"""Email (via Flask-Mail -> Mailpit) and web push. Failures are logged, never raised."""
import json
import logging
from urllib.parse import urlsplit

from flask import current_app
from flask_mail import Message
from pywebpush import WebPushException, webpush

from . import email_templates, settings
from .extensions import db, mail
from .models import PushSubscription, User

log = logging.getLogger(__name__)


def external_url(endpoint, **values):
    """Absolute URL using BASE_URL, so it works from CLI jobs as well as requests."""
    base = urlsplit(current_app.config["BASE_URL"])
    adapter = current_app.url_map.bind(
        base.netloc, script_name=base.path or "/", url_scheme=base.scheme or "http"
    )
    return adapter.build(endpoint, values, force_external=True)


def send_email(to, subject, body):
    recipients = [a.strip() for a in (to if isinstance(to, list) else str(to).split(",")) if a and a.strip()]
    if not recipients:
        return False
    try:
        mail.send(Message(subject=subject, recipients=recipients, body=body))
        return True
    except Exception:  # never let email break a request or the daily job
        log.exception("Could not send email to %s", recipients)
        return False


def email_user(template, user, **context):
    if not user or not user.email:
        return False
    context.setdefault("member_name", user.name)
    subject, body = email_templates.render(template, **context)
    return send_email(user.email, subject, body)


def librarian_address():
    return settings.get("librarian_email") or current_app.config["LIBRARIAN_EMAIL"]


def email_librarian(template, **context):
    subject, body = email_templates.render(template, **context)
    return send_email(librarian_address(), subject, body)


def push_to_user(user, title, body, url="/"):
    """Send a push to every device this user has subscribed. Returns number delivered."""
    private_key = current_app.config.get("VAPID_PRIVATE_KEY")
    if not private_key:
        log.info("Push skipped: VAPID keys are not set")
        return 0
    payload = json.dumps({"title": title, "body": body, "url": url})
    delivered = 0
    for sub in list(user.push_subscriptions):
        try:
            webpush(
                subscription_info=sub.as_subscription_info(),
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": current_app.config["VAPID_CLAIM_EMAIL"]},
                timeout=10,
            )
            delivered += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            log.warning("Push failed (%s); removing subscription %s", status, sub.id)
            db.session.delete(sub)
        except Exception:
            log.exception("Push failed; removing subscription %s", sub.id)
            db.session.delete(sub)
    db.session.commit()
    return delivered


def push_admins(title, body, url="/"):
    delivered = 0
    for admin in User.query.filter_by(role="admin").all():
        try:
            delivered += push_to_user(admin, title, body, url)
        except Exception:
            log.exception("Push to admin %s failed", admin.id)
    return delivered
