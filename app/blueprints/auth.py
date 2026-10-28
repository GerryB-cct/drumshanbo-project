from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .. import notify
from ..dates import today
from ..extensions import db
from ..forms import ApplyForm, ForgotForm, LoginForm, ResetForm
from ..models import User
from . import test_mode_required

bp = Blueprint("auth", __name__, url_prefix="/account")

TEST_MEMBER_EMAIL = "member@example.com"
TEST_LIBRARIAN_EMAIL = "librarian@example.com"


def normalise_email(email):
    return (email or "").strip().lower()


def _safe_next(target):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


def _after_login(user):
    if user.is_admin and not request.args.get("next"):
        return redirect(url_for("admin.dashboard"))
    return redirect(_safe_next(request.args.get("next")) or url_for("main.home"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=normalise_email(form.email.data)).first()
        if user is None or not user.check_password(form.password.data):
            flash("That email and password don't match. Please try again.", "error")
        elif user.status == "pending":
            flash("Your application is still waiting for the librarian to approve it. "
                  "We'll email you when it's approved.", "info")
        elif user.status not in ("active", "suspended"):
            flash("This account can't be used to log in. Please contact the librarian.", "error")
        else:
            login_user(user, remember=form.remember.data)
            return _after_login(user)
    return render_template("auth/login.html", form=form)


@bp.route("/test-login/<who>", methods=["POST"])
@test_mode_required
def test_login(who):
    email = TEST_LIBRARIAN_EMAIL if who == "librarian" else TEST_MEMBER_EMAIL
    user = User.query.filter_by(email=email).first()
    if user is None:
        flash("Test accounts are missing. Run `flask seed` first.", "error")
        return redirect(url_for("auth.login"))
    login_user(user, remember=True)
    return _after_login(user)


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("You have logged out.", "info")
    return redirect(url_for("main.home"))


@bp.route("/apply", methods=["GET", "POST"])
def apply():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = ApplyForm()
    if form.validate_on_submit():
        email = normalise_email(form.email.data)
        existing = User.query.filter_by(email=email).first()
        if existing and existing.status != "rejected":
            flash("There is already an account or application with that email address. "
                  "Try logging in, or use \"Forgotten password\".", "error")
            return render_template("auth/apply.html", form=form)
        if existing:  # a previously rejected applicant may apply again
            db.session.delete(existing)
            db.session.flush()
        user = User(
            name=form.name.data.strip(),
            address=form.address.data.strip(),
            email=email,
            phone=form.phone.data.strip(),
            role="member",
            status="pending",
            adult_confirmed=True,
            consent_at=datetime.now(),
            applied_on=today(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        notify.email_user("application_received", user)
        link = notify.external_url("admin.applications")
        notify.email_librarian("librarian_new_application", applicant_name=user.name, link=link)
        notify.push_admins("New membership application", f"{user.name} has applied to join.", url=link)
        return redirect(url_for("auth.apply_done"))
    return render_template("auth/apply.html", form=form)


@bp.route("/apply/thanks")
def apply_done():
    return render_template("auth/apply_done.html")


# --- Password reset ---------------------------------------------------------

def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")


def make_reset_token(user):
    # Only the user id and a fingerprint of the current password hash: no personal data
    # in the URL, and the link stops working once the password has been changed.
    return _serializer().dumps([user.id, (user.password_hash or "")[-12:]])


def user_from_reset_token(token):
    try:
        user_id, fingerprint = _serializer().loads(
            token, max_age=current_app.config["PASSWORD_RESET_MAX_AGE"]
        )
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None
    user = db.session.get(User, user_id)
    if user is None or (user.password_hash or "")[-12:] != fingerprint:
        return None
    return user


@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    form = ForgotForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=normalise_email(form.email.data)).first()
        if user and user.status in ("active", "suspended"):
            link = notify.external_url("auth.reset", token=make_reset_token(user))
            notify.email_user("password_reset", user, link=link)
        # Same message either way, so nobody can test which emails are members.
        flash("If that email belongs to a member, we've sent a link to reset the password. "
              "It works for one hour.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html", form=form)


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    user = user_from_reset_token(token)
    if user is None:
        flash("That reset link has expired or has already been used. Please ask for a new one.", "error")
        return redirect(url_for("auth.forgot"))
    form = ResetForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been changed. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", form=form)
