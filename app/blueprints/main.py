from flask import Blueprint, current_app, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user
from sqlalchemy import or_

from .. import settings
from ..dates import today
from ..lending import book_for_member
from ..models import BOOK_TYPES, HIDDEN_STATUSES, LOAN_ON_LOAN, Book

bp = Blueprint("main", __name__)

PER_PAGE = 25


def search_books(q="", book_type=""):
    query = Book.query.filter(Book.status.notin_(HIDDEN_STATUSES))
    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Book.title.ilike(like), Book.author.ilike(like), Book.isbn.ilike(like)))
    if book_type in BOOK_TYPES:
        query = query.filter(Book.book_type == book_type)
    return query.order_by(Book.title)


@bp.route("/")
def home():
    if not current_user.is_authenticated:
        return render_template("main/home_public.html")
    loans = current_user.open_loans()
    holds = [
        r for r in current_user.requests
        if r.status == "on_hold"
    ]
    waiting = [r for r in current_user.requests if r.status == "waiting"]
    return render_template(
        "main/home_member.html",
        loans=loans,
        holds=holds,
        waiting=waiting,
        today=today(),
        amber_days=settings.get_int("remind_due_soon_days"),
        renewals_allowed=settings.get_int("renewals_allowed"),
        LOAN_ON_LOAN=LOAN_ON_LOAN,
    )


@bp.route("/catalogue")
def catalogue():
    q = request.args.get("q", "")
    book_type = request.args.get("type", "")
    page = request.args.get("page", 1, type=int)
    pagination = search_books(q, book_type).paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template(
        "main/catalogue.html", pagination=pagination, q=q, book_type=book_type, types=BOOK_TYPES
    )


@bp.route("/book/<int:book_id>")
def book_detail(book_id):
    book = book_for_member(book_id)
    if book is None:
        return render_template("main/error.html", title="Book not found",
                               message="Sorry, we couldn't find that book."), 404
    if current_user.is_authenticated:
        # Members see the book page with its Borrow / Request buttons.
        return redirect(url_for("member.borrow_confirm", book_id=book.id))
    return render_template("main/book.html", book=book)


@bp.route("/privacy")
def privacy():
    return render_template("main/privacy.html", librarian_email=settings.get("librarian_email"))


@bp.route("/offline")
def offline():
    return render_template("main/offline.html")


# Served from the site root so the service worker controls the whole app.
@bp.route("/sw.js")
def service_worker():
    response = send_from_directory(current_app.static_folder, "js/sw.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@bp.route("/manifest.json")
def manifest():
    return send_from_directory(current_app.static_folder, "manifest.json", mimetype="application/manifest+json")
