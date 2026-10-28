from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user

from .. import lending, settings
from ..dates import today
from ..extensions import db
from ..forms import DetailsForm, PasswordChangeForm
from ..lending import LendingError, book_for_member
from ..models import LOAN_ON_LOAN, OPEN_LOAN_STATUSES, Loan, User
from .auth import normalise_email
from .main import search_books

bp = Blueprint("member", __name__)


@bp.before_request
@login_required
def require_login():
    pass


def _my_loan(loan_id, status=None):
    loan = db.session.get(Loan, loan_id)
    if loan is None or loan.user_id != current_user.id:
        abort(404)
    if status and loan.status != status:
        abort(404)
    return loan


# --- Borrow -----------------------------------------------------------------

@bp.route("/borrow")
def borrow_search():
    q = request.args.get("q", "").strip()
    results = search_books(q).limit(40).all() if q else []
    return render_template("member/borrow_search.html", q=q, results=results)


@bp.route("/borrow/<int:book_id>", methods=["GET", "POST"])
def borrow_confirm(book_id):
    book = book_for_member(book_id)
    if book is None:
        abort(404)
    if request.method == "POST":
        try:
            loan = lending.borrow(current_user, book)
        except LendingError as exc:
            flash(str(exc), "error")
            return redirect(url_for("member.borrow_confirm", book_id=book.id))
        return redirect(url_for("member.borrow_done", loan_id=loan.id))
    problem = lending.borrow_problem(current_user, book)
    request_problem = None
    if problem and book.status in ("on_loan", "awaiting_check"):
        request_problem = lending.request_problem(current_user, book)
    return render_template(
        "member/borrow_confirm.html",
        book=book,
        problem=problem,
        can_request=bool(problem) and book.status in ("on_loan", "awaiting_check") and request_problem is None,
        request_problem=request_problem,
        loan_weeks=settings.get_int("loan_weeks"),
        hold_days=settings.get_int("hold_days"),
    )


@bp.route("/borrow/done/<int:loan_id>")
def borrow_done(loan_id):
    return render_template("member/borrow_done.html", loan=_my_loan(loan_id))


# --- Request ----------------------------------------------------------------

@bp.route("/request/<int:book_id>", methods=["POST"])
def request_book(book_id):
    book = book_for_member(book_id)
    if book is None:
        abort(404)
    try:
        lending.request_book(current_user, book)
    except LendingError as exc:
        flash(str(exc), "error")
        return redirect(url_for("member.borrow_confirm", book_id=book.id))
    return render_template("member/request_done.html", book=book, hold_days=settings.get_int("hold_days"))


# --- Return -----------------------------------------------------------------

@bp.route("/return")
def return_list():
    loans = current_user.current_loans()
    return render_template("member/return_list.html", loans=loans, today=today())


@bp.route("/return/<int:loan_id>", methods=["GET", "POST"])
def return_confirm(loan_id):
    loan = _my_loan(loan_id)
    if loan.status != LOAN_ON_LOAN:
        flash("This book has already been returned.", "info")
        return redirect(url_for("main.home"))
    if request.method == "POST":
        try:
            lending.return_book(current_user, loan, request.form.get("damage_note", "")[:1000])
        except LendingError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.home"))
        return redirect(url_for("member.return_done", loan_id=loan.id))
    return render_template("member/return_confirm.html", loan=loan)


@bp.route("/return/done/<int:loan_id>")
def return_done(loan_id):
    return render_template("member/return_done.html", loan=_my_loan(loan_id))


# --- Renew (only shown if renewals are switched on in Settings) -------------

@bp.route("/renew/<int:loan_id>", methods=["POST"])
def renew(loan_id):
    loan = _my_loan(loan_id)
    try:
        lending.renew(current_user, loan)
        flash(f"Renewed. \"{loan.book.title}\" is now due back on {loan.due_on:%d %B %Y}.", "success")
    except LendingError as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.home"))


# --- Lost -------------------------------------------------------------------

@bp.route("/lost/<int:loan_id>", methods=["GET", "POST"])
def lost_confirm(loan_id):
    loan = _my_loan(loan_id)
    if loan.status != LOAN_ON_LOAN:
        abort(404)
    if request.method == "POST":
        try:
            lending.report_lost(current_user, loan)
        except LendingError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.home"))
        flash("Thank you for letting us know. The librarian will be in touch about "
              f"\"{loan.book.title}\".", "success")
        return redirect(url_for("main.home"))
    return render_template("member/lost_confirm.html", loan=loan)


# --- History ----------------------------------------------------------------

@bp.route("/history")
def history():
    loans = current_user.loans.order_by(Loan.borrowed_on.desc()).all()
    return render_template("member/history.html", loans=loans)


# --- My details -------------------------------------------------------------

@bp.route("/details", methods=["GET", "POST"])
def details():
    form = DetailsForm(obj=current_user)
    pw_form = PasswordChangeForm(prefix="pw")
    if form.validate_on_submit():
        email = normalise_email(form.email.data)
        clash = User.query.filter(User.email == email, User.id != current_user.id).first()
        if clash:
            flash("That email address is already used by another account.", "error")
        else:
            current_user.name = form.name.data.strip()
            current_user.address = form.address.data.strip()
            current_user.phone = form.phone.data.strip()
            current_user.email = email
            db.session.commit()
            flash("Your details have been saved.", "success")
            return redirect(url_for("member.details"))
    return render_template("member/details.html", form=form, pw_form=pw_form)


@bp.route("/details/password", methods=["POST"])
def change_password():
    form = DetailsForm(obj=current_user, formdata=None)
    pw_form = PasswordChangeForm(prefix="pw")
    if pw_form.validate_on_submit():
        if not current_user.check_password(pw_form.current.data):
            pw_form.current.errors.append("That isn't your current password.")
        else:
            current_user.set_password(pw_form.password.data)
            db.session.commit()
            flash("Your password has been changed.", "success")
            return redirect(url_for("member.details"))
    return render_template("member/details.html", form=form, pw_form=pw_form)


@bp.route("/details/close", methods=["GET", "POST"])
def close_account():
    has_books = current_user.loans.filter(Loan.status.in_(OPEN_LOAN_STATUSES)).count() > 0
    if request.method == "POST":
        if request.form.get("confirm") != "yes":
            flash("Please tick the box to confirm.", "error")
            return redirect(url_for("member.close_account"))
        try:
            lending.close_account(current_user._get_current_object())
        except LendingError as exc:
            flash(str(exc), "error")
            return redirect(url_for("member.close_account"))
        logout_user()
        return render_template("member/closed.html")
    return render_template("member/close_account.html", has_books=has_books)
