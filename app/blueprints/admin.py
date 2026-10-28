import csv
import io
import os
import secrets
from datetime import date

import requests
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user
from sqlalchemy import or_

from .. import csv_import, email_templates, isbn, lending, notify, reminders, settings
from ..dates import add_days, short_date, today
from ..extensions import db
from ..forms import AdminCreateForm, BookForm, CsvUploadForm, DetailsForm
from ..lending import LendingError
from ..models import (
    ACTIVE_REQUEST_STATUSES,
    BOOK_STATUSES,
    BOOK_TYPES,
    LOAN_LOST_REPORTED,
    LOAN_ON_LOAN,
    LOAN_RETURNED_PENDING,
    Book,
    BookRequest,
    Loan,
    PushSubscription,
    User,
)
from . import admin_required, test_mode_required
from .auth import normalise_email

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@admin_required
def require_admin():
    pass


def _get_or_404(model, ident):
    obj = db.session.get(model, ident)
    if obj is None:
        abort(404)
    return obj


def _members_query():
    return User.query.filter(User.role.in_(["member", "admin"]))


# --------------------------------------------------------------------------
# Dashboard and test tools
# --------------------------------------------------------------------------

def dashboard_counts():
    now = today()
    cutoff = reminders.long_overdue_cutoff(now)
    on_loan = Loan.query.filter(Loan.status == LOAN_ON_LOAN)
    return {
        "pending": User.query.filter_by(status="pending").count(),
        "out": on_loan.count(),
        "awaiting": Loan.query.filter(Loan.status == LOAN_RETURNED_PENDING).count(),
        "overdue": on_loan.filter(Loan.due_on < now).count(),
        "long": on_loan.filter(Loan.due_on <= cutoff).count(),
        "requests": BookRequest.query.filter(BookRequest.status == "waiting").count(),
        "holds": BookRequest.query.filter(BookRequest.status == "on_hold").count(),
        "lost": Loan.query.filter(Loan.status == LOAN_LOST_REPORTED).count(),
    }


@bp.route("/")
def dashboard():
    return render_template("admin/dashboard.html", counts=dashboard_counts())


@bp.route("/test/pretend-today", methods=["POST"])
@test_mode_required
def pretend_today():
    if request.form.get("action") == "clear":
        settings.delete("pretend_today")
        db.session.commit()
        flash("Back to the real date.", "success")
    else:
        value = request.form.get("date", "")
        try:
            chosen = date.fromisoformat(value)
        except ValueError:
            flash("Please choose a date.", "error")
            return redirect(url_for("admin.dashboard"))
        settings.set("pretend_today", chosen.isoformat())
        db.session.commit()
        flash(f"Pretending today is {short_date(chosen)}.", "success")
    return redirect(request.form.get("back") or url_for("admin.dashboard"))


@bp.route("/test/shift-days", methods=["POST"])
@test_mode_required
def shift_days():
    days = request.form.get("days", 0, type=int)
    settings.set("pretend_today", add_days(today(), days).isoformat())
    db.session.commit()
    flash(f"Pretending today is {short_date(today())}.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/test/run-reminders", methods=["POST"])
@test_mode_required
def run_reminders():
    summary = reminders.run_daily()
    flash("\n".join(reminders.summary_lines(summary)), "success")
    return redirect(url_for("admin.dashboard"))


# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------

@bp.route("/applications")
def applications():
    pending = User.query.filter_by(status="pending").order_by(User.applied_on).all()
    rejected = User.query.filter_by(status="rejected").order_by(User.rejected_on.desc()).all()
    return render_template("admin/applications.html", pending=pending, rejected=rejected)


@bp.route("/applications/<int:user_id>/approve", methods=["POST"])
def approve(user_id):
    user = _get_or_404(User, user_id)
    if user.status != "pending":
        flash("That application has already been dealt with.", "info")
        return redirect(url_for("admin.applications"))
    user.status = "active"
    user.approved_on = today()
    db.session.commit()
    notify.email_user("application_approved", user, link=notify.external_url("auth.login"))
    flash(f"{user.name} is now a member and has been emailed.", "success")
    return redirect(url_for("admin.applications"))


@bp.route("/applications/<int:user_id>/reject", methods=["POST"])
def reject(user_id):
    user = _get_or_404(User, user_id)
    if user.status != "pending":
        flash("That application has already been dealt with.", "info")
        return redirect(url_for("admin.applications"))
    reason = request.form.get("reason", "").strip()[:1000]
    user.status = "rejected"
    user.rejected_on = today()
    user.reject_reason = reason or None
    db.session.commit()
    notify.email_user("application_rejected", user, reason=f"Reason: {reason}" if reason else "")
    flash(f"{user.name}'s application was not approved. They have been emailed. "
          "It will be deleted automatically after 30 days.", "success")
    return redirect(url_for("admin.applications"))


# --------------------------------------------------------------------------
# Members
# --------------------------------------------------------------------------

@bp.route("/members", methods=["GET", "POST"])
def members():
    # Search terms are POSTed so names never appear in URLs.
    q = request.form.get("q", "").strip() if request.method == "POST" else ""
    status = request.args.get("status", "")
    query = _members_query().filter(User.status.in_(["active", "suspended"]))
    if status in ("active", "suspended"):
        query = query.filter(User.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like), User.phone.ilike(like)))
    people = query.order_by(User.name).all()
    return render_template("admin/members.html", people=people, q=q, status=status, today=today())


@bp.route("/members/<int:user_id>")
def member_detail(user_id):
    user = _get_or_404(User, user_id)
    if user.role == "placeholder":
        abort(404)
    loans = user.loans.order_by(Loan.borrowed_on.desc()).all()
    reqs = user.requests.order_by(BookRequest.id.desc()).all()
    return render_template("admin/member_detail.html", user=user, loans=loans, reqs=reqs, today=today())


@bp.route("/members/<int:user_id>/edit", methods=["GET", "POST"])
def member_edit(user_id):
    user = _get_or_404(User, user_id)
    if user.role == "placeholder":
        abort(404)
    form = DetailsForm(obj=user)
    if form.validate_on_submit():
        email = normalise_email(form.email.data)
        if User.query.filter(User.email == email, User.id != user.id).first():
            flash("That email address is already used by another account.", "error")
        else:
            user.name = form.name.data.strip()
            user.address = form.address.data.strip()
            user.phone = form.phone.data.strip()
            user.email = email
            db.session.commit()
            flash("Details saved.", "success")
            return redirect(url_for("admin.member_detail", user_id=user.id))
    return render_template("admin/member_edit.html", form=form, user=user)


@bp.route("/members/<int:user_id>/suspend", methods=["POST"])
def member_suspend(user_id):
    user = _get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You can't suspend yourself.", "error")
    elif user.status == "active":
        user.status = "suspended"
        db.session.commit()
        flash(f"{user.name} is suspended. They can log in and see their books but can't borrow or request.", "success")
    return redirect(url_for("admin.member_detail", user_id=user.id))


@bp.route("/members/<int:user_id>/reactivate", methods=["POST"])
def member_reactivate(user_id):
    user = _get_or_404(User, user_id)
    if user.status == "suspended":
        user.status = "active"
        db.session.commit()
        flash(f"{user.name} can borrow again.", "success")
    return redirect(url_for("admin.member_detail", user_id=user.id))


@bp.route("/admins/new", methods=["GET", "POST"])
def admin_create():
    form = AdminCreateForm()
    if form.validate_on_submit():
        email = normalise_email(form.email.data)
        if User.query.filter_by(email=email).first():
            flash("That email address is already used by another account.", "error")
        else:
            user = User(
                name=form.name.data.strip(),
                address=form.address.data.strip(),
                email=email,
                phone=form.phone.data.strip(),
                role="admin",
                status="active",
                adult_confirmed=True,
                applied_on=today(),
                approved_on=today(),
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash(f"{user.name} is now a librarian (admin). Give them their password in person.", "success")
            return redirect(url_for("admin.settings_page"))
    return render_template("admin/admin_create.html", form=form)


# --------------------------------------------------------------------------
# Books
# --------------------------------------------------------------------------

@bp.route("/books")
def books():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)
    query = Book.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Book.title.ilike(like), Book.author.ilike(like), Book.isbn.ilike(like)))
    if status in BOOK_STATUSES:
        query = query.filter(Book.status == status)
    pagination = query.order_by(Book.title).paginate(page=page, per_page=30, error_out=False)
    return render_template("admin/books.html", pagination=pagination, q=q, status=status, statuses=BOOK_STATUSES)


@bp.route("/books/new", methods=["GET", "POST"])
def book_new():
    form = BookForm()
    if form.validate_on_submit():
        book = Book(status="available")
        _fill_book(book, form)
        db.session.add(book)
        db.session.commit()
        flash(f"Added \"{book.title}\".", "success")
        if request.form.get("another"):
            return redirect(url_for("admin.book_new"))
        return redirect(url_for("admin.books"))
    return render_template("admin/book_form.html", form=form, book=None)


@bp.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
def book_edit(book_id):
    book = _get_or_404(Book, book_id)
    form = BookForm(obj=book)
    if form.validate_on_submit():
        _fill_book(book, form)
        db.session.commit()
        flash("Book saved.", "success")
        return redirect(url_for("admin.books"))
    loans = book.loans.order_by(Loan.borrowed_on.desc()).limit(20).all()
    return render_template("admin/book_form.html", form=form, book=book, loans=loans,
                           has_history=book.loans.count() > 0)


def _fill_book(book, form):
    book.title = form.title.data.strip()
    book.author = (form.author.data or "").strip()
    book.book_type = form.book_type.data if form.book_type.data in BOOK_TYPES else "tune book"
    book.isbn = csv_import.normalise_isbn(form.isbn.data)
    book.notes = (form.notes.data or "").strip() or None
    book.cover_url = (form.cover_url.data or "").strip() or None


@bp.route("/books/<int:book_id>/delete", methods=["POST"])
def book_delete(book_id):
    book = _get_or_404(Book, book_id)
    if book.loans.count() or book.requests.count():
        flash("This book has loan history, so it can't be deleted. Mark it as withdrawn instead.", "error")
        return redirect(url_for("admin.book_edit", book_id=book.id))
    db.session.delete(book)
    db.session.commit()
    flash(f"Deleted \"{book.title}\".", "success")
    return redirect(url_for("admin.books"))


@bp.route("/books/<int:book_id>/status", methods=["GET", "POST"])
def book_status(book_id):
    book = _get_or_404(Book, book_id)
    if request.method == "POST":
        action = request.form.get("action")
        member = None
        if action == "borrowed":
            member = db.session.get(User, request.form.get("member_id", type=int) or 0)
        try:
            lending.override_status(book, action, member)
            flash(f"\"{book.title}\" is now: {book.status.replace('_', ' ')}.", "success")
        except LendingError as exc:
            flash(str(exc), "error")
        return redirect(url_for("admin.book_status", book_id=book.id))
    people = _members_query().filter(User.status.in_(["active", "suspended"])).order_by(User.name).all()
    return render_template("admin/book_status.html", book=book, loan=book.open_loan(),
                           req=book.active_request(), people=people)


@bp.route("/isbn-lookup")
def isbn_lookup():
    code = request.args.get("isbn", "")
    try:
        result = isbn.lookup(code)
    except requests.RequestException:
        return jsonify({"ok": False, "message": "Couldn't reach Open Library. Check the internet "
                                                "connection, or enter the details manually."}), 502
    if not result:
        return jsonify({"ok": False, "message": "Not found — enter details manually."}), 404
    existing = Book.query.filter_by(isbn=result["isbn"]).first()
    result["ok"] = True
    if existing:
        result["warning"] = f"Note: \"{existing.title}\" already has this ISBN in the catalogue."
    return jsonify(result)


# --- CSV import ---------------------------------------------------------------

def _upload_dir():
    path = os.path.join(current_app.instance_path, "uploads")
    os.makedirs(path, exist_ok=True)
    return path


def _upload_path():
    token = session.get("import_token")
    if not token or not token.isalnum():
        return None
    path = os.path.join(_upload_dir(), f"{token}.csv")
    return path if os.path.exists(path) else None


@bp.route("/books/import", methods=["GET", "POST"])
def book_import():
    form = CsvUploadForm()
    if form.validate_on_submit():
        text = csv_import.decode(form.file.data.read())
        headers, rows = csv_import.read_csv(text)
        if not headers or not rows:
            flash("That file looks empty. It needs a header row and at least one book.", "error")
            return render_template("admin/import_upload.html", form=form)
        token = secrets.token_hex(16)
        with open(os.path.join(_upload_dir(), f"{token}.csv"), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        session["import_token"] = token
        return redirect(url_for("admin.book_import_map"))
    return render_template("admin/import_upload.html", form=form)


@bp.route("/books/import/map", methods=["GET", "POST"])
def book_import_map():
    path = _upload_path()
    if not path:
        flash("Please upload the CSV file again.", "error")
        return redirect(url_for("admin.book_import"))
    with open(path, encoding="utf-8", newline="") as fh:
        headers, rows = csv_import.read_csv(fh.read())

    if request.method == "POST":
        mapping = {}
        for field, _label, _req in csv_import.FIELDS:
            value = request.form.get(f"map_{field}", "")
            mapping[field] = int(value) if value.isdigit() and int(value) < len(headers) else None
        default_type = request.form.get("default_type")
        if default_type not in BOOK_TYPES:
            default_type = "tune book"
    else:
        mapping = csv_import.guess_mapping(headers)
        default_type = "tune book"

    if request.method == "POST" and request.form.get("action") == "import":
        if mapping["title"] is None:
            flash("Please choose which column holds the title.", "error")
        else:
            imported, skipped = csv_import.import_rows(rows, mapping, default_type)
            os.remove(path)
            session.pop("import_token", None)
            return render_template("admin/import_result.html", imported=imported, skipped=skipped,
                                   total=len(rows))

    preview = csv_import.preview(rows, mapping, default_type) if mapping["title"] is not None else []
    return render_template(
        "admin/import_map.html",
        headers=headers,
        fields=csv_import.FIELDS,
        mapping=mapping,
        default_type=default_type,
        types=BOOK_TYPES,
        preview=preview,
        total=len(rows),
    )


# --------------------------------------------------------------------------
# Loans
# --------------------------------------------------------------------------

LOAN_VIEWS = {
    "current": "On loan",
    "overdue": "Overdue",
    "long": "Long overdue",
    "awaiting": "Awaiting check",
    "lost": "Lost reports",
    "requests": "Requests & holds",
}


@bp.route("/loans")
def loans():
    view = request.args.get("view", "current")
    if view not in LOAN_VIEWS:
        view = "current"
    now = today()
    on_loan = Loan.query.filter(Loan.status == LOAN_ON_LOAN)
    items = []
    if view == "current":
        items = on_loan.order_by(Loan.due_on).all()
    elif view == "overdue":
        items = on_loan.filter(Loan.due_on < now).order_by(Loan.due_on).all()
    elif view == "long":
        items = on_loan.filter(Loan.due_on <= reminders.long_overdue_cutoff(now)).order_by(Loan.due_on).all()
    elif view == "awaiting":
        items = Loan.query.filter(Loan.status == LOAN_RETURNED_PENDING).order_by(Loan.returned_on).all()
    elif view == "lost":
        items = Loan.query.filter(Loan.status == LOAN_LOST_REPORTED).order_by(Loan.lost_reported_on).all()
    elif view == "requests":
        items = (
            BookRequest.query.filter(BookRequest.status.in_(ACTIVE_REQUEST_STATUSES))
            .order_by(BookRequest.created_on)
            .all()
        )
    return render_template("admin/loans.html", view=view, views=LOAN_VIEWS, items=items, today=now,
                           counts=dashboard_counts())


@bp.route("/loans/<int:loan_id>/check")
def loan_check(loan_id):
    loan = _get_or_404(Loan, loan_id)
    return render_template("admin/loan_check.html", loan=loan, req=loan.book.active_request())


def _loan_action(loan_id, func, message):
    loan = _get_or_404(Loan, loan_id)
    try:
        func(loan)
        flash(message.format(title=loan.book.title, name=loan.user.name), "success")
    except LendingError as exc:
        flash(str(exc), "error")
    return redirect(request.form.get("back") or url_for("admin.loans", view="awaiting"))


@bp.route("/loans/<int:loan_id>/confirm", methods=["POST"])
def loan_confirm(loan_id):
    return _loan_action(loan_id, lending.confirm_on_shelf, "\"{title}\" is back on the shelf.")


@bp.route("/loans/<int:loan_id>/not-received", methods=["POST"])
def loan_not_received(loan_id):
    return _loan_action(loan_id, lending.not_received,
                        "\"{title}\" is on loan to {name} again, and they have been emailed.")


@bp.route("/loans/<int:loan_id>/lost-found", methods=["POST"])
def loan_lost_found(loan_id):
    return _loan_action(loan_id, lending.lost_found, "\"{title}\" has been found and is back on the shelf.")


@bp.route("/loans/<int:loan_id>/lost-confirm", methods=["POST"])
def loan_lost_confirm(loan_id):
    return _loan_action(loan_id, lending.lost_confirm,
                        "\"{title}\" is recorded as lost. It is hidden from the catalogue.")


@bp.route("/requests/<int:req_id>/cancel", methods=["POST"])
def request_cancel(req_id):
    req = _get_or_404(BookRequest, req_id)
    lending.cancel_request(req)
    flash(f"Request for \"{req.book.title}\" cancelled.", "success")
    return redirect(url_for("admin.loans", view="requests"))


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

@bp.route("/settings", methods=["GET", "POST"])
def settings_page():
    if request.method == "POST":
        errors = []
        values = {}
        for key in settings.INT_KEYS:
            raw = request.form.get(key, "").strip()
            if not raw.isdigit():
                errors.append(f"\"{settings.LABELS[key]}\" must be a whole number.")
                continue
            values[key] = int(raw)
        if not errors:
            if values["loan_weeks"] < 1 or values["max_books"] < 1 or values["hold_days"] < 1:
                errors.append("Loan period, book limit and hold period must be at least 1.")
            if not values["remind_overdue1_days"] < values["remind_overdue2_days"] < values["remind_final_days"]:
                errors.append("Overdue reminder days must go up: 1st < 2nd < final.")
            if values["remind_overdue1_days"] < 1:
                errors.append("The 1st overdue email must be at least 1 day after the due date.")
        email = request.form.get("librarian_email", "").strip()
        if "@" not in email:
            errors.append("Please enter the librarian's email address.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            for key, value in values.items():
                settings.set(key, value)
            for key in settings.BOOL_KEYS:
                settings.set(key, "1" if request.form.get(key) else "0")
            settings.set("librarian_email", email)
            db.session.commit()
            flash("Settings saved.", "success")
            return redirect(url_for("admin.settings_page"))
    current = {key: settings.get(key) for key in settings.INT_KEYS}
    bools = {key: settings.get_bool(key) for key in settings.BOOL_KEYS}
    admins = User.query.filter_by(role="admin").order_by(User.name).all()
    return render_template(
        "admin/settings.html",
        labels=settings.LABELS,
        int_keys=settings.INT_KEYS,
        bool_keys=settings.BOOL_KEYS,
        current=current,
        bools=bools,
        librarian_email=settings.get("librarian_email"),
        admins=admins,
    )


@bp.route("/settings/emails", methods=["GET", "POST"])
def email_settings():
    if request.method == "POST":
        name = request.form.get("name")
        if name not in email_templates.TEMPLATES:
            abort(400)
        if request.form.get("action") == "reset":
            settings.delete(f"email:{name}:subject")
            settings.delete(f"email:{name}:body")
            flash("Wording reset to the default.", "success")
        else:
            subject = request.form.get("subject", "").strip()
            body = request.form.get("body", "").replace("\r\n", "\n").strip()
            if not subject or not body:
                flash("Subject and message can't be empty.", "error")
                return redirect(url_for("admin.email_settings") + f"#tpl-{name}")
            settings.set(f"email:{name}:subject", subject)
            settings.set(f"email:{name}:body", body)
            flash("Email wording saved.", "success")
        db.session.commit()
        return redirect(url_for("admin.email_settings") + f"#tpl-{name}")
    templates = []
    for name, meta in email_templates.TEMPLATES.items():
        subject, body = email_templates.get_template(name)
        templates.append({
            "name": name,
            "label": meta["label"],
            "placeholders": meta["placeholders"] + ["signature"],
            "subject": subject,
            "body": body,
            "customised": subject != meta["subject"] or body != meta["body"],
        })
    return render_template("admin/email_settings.html", templates=templates)


# --------------------------------------------------------------------------
# CSV export
# --------------------------------------------------------------------------

def _csv_response(filename, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        "﻿" + buf.getvalue(),  # BOM so Excel reads the Irish fadas correctly
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/export/<kind>.csv")
def export(kind):
    stamp = today().isoformat()
    if kind == "members":
        people = _members_query().order_by(User.name).all()
        return _csv_response(
            f"members-{stamp}.csv",
            ["id", "name", "email", "phone", "address", "role", "status", "applied_on", "approved_on", "consent_at"],
            [[u.id, u.name, u.email, u.phone, u.address, u.role, u.status, u.applied_on, u.approved_on,
              u.consent_at.isoformat(timespec="seconds") if u.consent_at else ""] for u in people],
        )
    if kind == "books":
        books = Book.query.order_by(Book.title).all()
        return _csv_response(
            f"books-{stamp}.csv",
            ["id", "title", "author", "type", "isbn", "status", "notes", "cover_url"],
            [[b.id, b.title, b.author, b.book_type, b.isbn or "", b.status, b.notes or "", b.cover_url or ""]
             for b in books],
        )
    if kind == "loans":
        loans = Loan.query.order_by(Loan.borrowed_on.desc()).all()
        return _csv_response(
            f"loans-{stamp}.csv",
            ["id", "book_id", "book_title", "member_id", "member_name", "borrowed_on", "due_on", "status",
             "returned_on", "closed_on", "damage_note", "reminders_sent"],
            [[l.id, l.book_id, l.book.title, l.user_id, l.user.name, l.borrowed_on, l.due_on, l.status,
              l.returned_on or "", l.closed_on or "", l.damage_note or "",
              " ".join(sorted(l.stages_sent()))] for l in loans],
        )
    abort(404)


# --------------------------------------------------------------------------
# Push notifications
# --------------------------------------------------------------------------

@bp.route("/push")
def push():
    subs = PushSubscription.query.filter_by(user_id=current_user.id).order_by(PushSubscription.created_at).all()
    return render_template("admin/push.html", subs=subs,
                           vapid_public_key=current_app.config["VAPID_PUBLIC_KEY"])


@bp.route("/push/subscribe", methods=["POST"])
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    keys = data.get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        return jsonify({"ok": False, "message": "That didn't work. Please try again."}), 400
    sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if sub is None:
        sub = PushSubscription(endpoint=endpoint)
        db.session.add(sub)
    sub.user_id = current_user.id
    sub.p256dh = keys["p256dh"]
    sub.auth = keys["auth"]
    sub.device_label = (request.headers.get("User-Agent") or "")[:255]
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/push/<int:sub_id>/remove", methods=["POST"])
def push_remove(sub_id):
    sub = _get_or_404(PushSubscription, sub_id)
    if sub.user_id != current_user.id:
        abort(404)
    db.session.delete(sub)
    db.session.commit()
    flash("That device will no longer get notifications.", "success")
    return redirect(url_for("admin.push"))


@bp.route("/push/test", methods=["POST"])
def push_test():
    if not current_app.config["VAPID_PRIVATE_KEY"]:
        flash("Push isn't set up yet: run `flask generate-vapid` and add the keys to .env.", "error")
        return redirect(request.form.get("back") or url_for("admin.push"))
    delivered = notify.push_to_user(
        current_user, "Test notification", "Push notifications are working on this device.",
        url=url_for("admin.dashboard"),
    )
    if delivered:
        flash(f"Test notification sent to {delivered} device(s).", "success")
    else:
        flash("No devices received it. Tap \"Enable notifications on this device\" first.", "error")
    return redirect(request.form.get("back") or url_for("admin.push"))
