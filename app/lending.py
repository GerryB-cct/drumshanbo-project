"""Lending rules and every state change to books, loans and requests.

Views call these functions; they never change statuses directly. Each function
raises LendingError with a plain-English message when an action is not allowed.
"""
from . import notify, settings
from .dates import add_days, nice_date, today
from .extensions import db
from .models import (
    ACTIVE_REQUEST_STATUSES,
    AVAILABLE,
    AWAITING_CHECK,
    LOAN_LOST,
    LOAN_LOST_REPORTED,
    LOAN_ON_LOAN,
    LOAN_RETURNED,
    LOAN_RETURNED_PENDING,
    LOST,
    ON_HOLD,
    ON_LOAN,
    OPEN_LOAN_STATUSES,
    REQ_CANCELLED,
    REQ_EXPIRED,
    REQ_FULFILLED,
    REQ_ON_HOLD,
    REQ_WAITING,
    WITHDRAWN,
    Book,
    BookRequest,
    Loan,
    User,
)

PLACEHOLDER_EMAIL = None  # the "former member" placeholder has no email
PLACEHOLDER_NAME = "Former member"


class LendingError(Exception):
    """An action the member or librarian tried is not allowed. Message is shown as-is."""


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def counted_loans(user):
    """Loans that count towards the limit and the overdue block (returned_pending does not)."""
    return user.loans.filter(Loan.status == LOAN_ON_LOAN).all()


def has_overdue(user, on_date=None):
    on_date = on_date or today()
    return any(loan.due_on < on_date for loan in counted_loans(user))


def borrow_problem(user, book):
    """Return a plain-English reason this user can't borrow this book, or None."""
    if user.status == "suspended":
        return (
            "Your membership is paused at the moment, so you can't borrow books. "
            "Please speak to the librarian."
        )
    if user.status != "active":
        return "Your membership isn't active yet."

    max_books = settings.get_int("max_books")
    if len(counted_loans(user)) >= max_books:
        return (
            f"You already have {max_books} books out, which is the most you can borrow at once. "
            "Please return one first."
        )
    if settings.get_bool("block_when_overdue") and has_overdue(user):
        return (
            "One of your books is overdue. Please return it before borrowing another."
        )

    if book.status == ON_HOLD:
        request = book.active_request()
        if request and request.user_id == user.id and request.status == REQ_ON_HOLD:
            return None
        return "This book is being held for someone who asked for it. Check back later."
    if book.status != AVAILABLE:
        return "Sorry, this book isn't on the shelf right now."

    if not settings.get_bool("allow_reborrow"):
        last = book.loans.order_by(Loan.id.desc()).first()
        if last and last.user_id == user.id:
            return "You've just returned this book, so you can't borrow it again straight away."
    return None


def request_problem(user, book):
    if user.status == "suspended":
        return (
            "Your membership is paused at the moment, so you can't request books. "
            "Please speak to the librarian."
        )
    if user.status != "active":
        return "Your membership isn't active yet."
    if book.status not in (ON_LOAN, AWAITING_CHECK):
        if book.status == AVAILABLE:
            return "This book is on the shelf, so you can borrow it now."
        return "This book can't be requested at the moment."
    loan = book.open_loan()
    if loan and loan.user_id == user.id:
        return "You have this book at the moment."
    request = book.active_request()
    if request:
        if request.user_id == user.id:
            return "You have already asked for this book. We'll email you when it's back."
        return "Someone has already asked for this book. Check back later."
    return None


# --------------------------------------------------------------------------
# Member actions
# --------------------------------------------------------------------------

def borrow(user, book):
    problem = borrow_problem(user, book)
    if problem:
        raise LendingError(problem)
    return _create_loan(user, book)


def _create_loan(user, book):
    start = today()
    request = book.active_request()
    loan = Loan(
        book=book,
        user=user,
        borrowed_on=start,
        due_on=add_days(start, settings.get_int("loan_weeks") * 7),
        status=LOAN_ON_LOAN,
    )
    if request and request.user_id == user.id:
        request.status = REQ_FULFILLED
        request.closed_on = start
    book.status = ON_LOAN
    db.session.add(loan)
    db.session.commit()
    return loan


def renew(user, loan):
    allowed = settings.get_int("renewals_allowed")
    if loan.user_id != user.id or loan.status != LOAN_ON_LOAN:
        raise LendingError("This loan can't be renewed.")
    if allowed <= 0:
        raise LendingError("Renewals aren't available.")
    if loan.renewals >= allowed:
        raise LendingError("You've already renewed this book as many times as allowed.")
    if loan.is_overdue(today()):
        raise LendingError("This book is overdue, so it can't be renewed. Please return it.")
    if loan.book.active_request():
        raise LendingError("Someone has asked for this book, so it can't be renewed.")
    loan.due_on = add_days(loan.due_on, settings.get_int("loan_weeks") * 7)
    loan.renewals += 1
    db.session.commit()
    return loan


def return_book(user, loan, damage_note=""):
    if loan.user_id != user.id or loan.status != LOAN_ON_LOAN:
        raise LendingError("This book isn't showing as on loan to you.")
    damage_note = (damage_note or "").strip()
    loan.status = LOAN_RETURNED_PENDING
    loan.returned_on = today()
    loan.damage_note = damage_note or None
    loan.book.status = AWAITING_CHECK
    db.session.commit()

    link = notify.external_url("admin.loan_check", loan_id=loan.id)
    notify.email_librarian(
        "librarian_return",
        member_name=user.name,
        book_title=loan.book.title,
        damage_note=damage_note or "none given",
        link=link,
    )
    notify.push_admins(
        "Book returned",
        f"\"{loan.book.title}\" — please check the shelf"
        + (" (damage noted)" if damage_note else ""),
        url=notify.external_url("admin.loan_check", loan_id=loan.id),
    )
    return loan


def request_book(user, book):
    problem = request_problem(user, book)
    if problem:
        raise LendingError(problem)
    request = BookRequest(book=book, user=user, status=REQ_WAITING, created_on=today())
    db.session.add(request)
    db.session.commit()

    loan = book.open_loan()
    if loan and loan.status == LOAN_ON_LOAN:
        # Never name the requester.
        notify.email_user(
            "nudge_borrower",
            loan.user,
            book_title=book.title,
            due_date=nice_date(loan.due_on),
        )
    return request


def report_lost(user, loan):
    if loan.user_id != user.id or loan.status != LOAN_ON_LOAN:
        raise LendingError("This book isn't showing as on loan to you.")
    loan.status = LOAN_LOST_REPORTED
    loan.lost_reported_on = today()
    loan.book.status = LOST
    db.session.commit()
    notify.email_librarian(
        "librarian_lost",
        member_name=user.name,
        book_title=loan.book.title,
        link=notify.external_url("admin.loans", view="lost"),
    )
    return loan


# --------------------------------------------------------------------------
# Librarian actions
# --------------------------------------------------------------------------

def shelve(book):
    """Book is physically back on the shelf: hold it for a waiting requester, or make it available."""
    request = (
        book.requests.filter(BookRequest.status == REQ_WAITING).order_by(BookRequest.id).first()
    )
    if request:
        start = today()
        hold_days = settings.get_int("hold_days")
        request.status = REQ_ON_HOLD
        request.hold_started_on = start
        request.hold_until = add_days(start, hold_days)
        book.status = ON_HOLD
        db.session.commit()
        notify.email_user(
            "hold_ready",
            request.user,
            book_title=book.title,
            hold_days=hold_days,
            hold_until=nice_date(request.hold_until),
            link=notify.external_url("member.borrow_confirm", book_id=book.id),
        )
    else:
        book.status = AVAILABLE
        db.session.commit()


def confirm_on_shelf(loan):
    if loan.status != LOAN_RETURNED_PENDING:
        raise LendingError("This return has already been dealt with.")
    loan.status = LOAN_RETURNED
    loan.closed_on = today()
    db.session.commit()
    shelve(loan.book)
    return loan


def not_received(loan):
    if loan.status != LOAN_RETURNED_PENDING:
        raise LendingError("This return has already been dealt with.")
    loan.status = LOAN_ON_LOAN  # original due date is kept
    loan.returned_on = None
    loan.book.status = ON_LOAN
    db.session.commit()
    notify.email_user(
        "not_received",
        loan.user,
        book_title=loan.book.title,
        due_date=nice_date(loan.due_on),
    )
    return loan


def lost_found(loan):
    """A book reported lost has turned up and is on the shelf."""
    if loan.status != LOAN_LOST_REPORTED:
        raise LendingError("This loan isn't marked as lost.")
    loan.status = LOAN_RETURNED
    loan.closed_on = today()
    db.session.commit()
    shelve(loan.book)


def lost_confirm(loan):
    """Accept that the book is gone. The loan is closed; the book stays 'lost' (hidden)."""
    if loan.status != LOAN_LOST_REPORTED:
        raise LendingError("This loan isn't marked as lost.")
    loan.status = LOAN_LOST
    loan.closed_on = today()
    _cancel_requests(loan.book)
    db.session.commit()


def _close_open_loan(book, as_status=LOAN_RETURNED):
    loan = book.open_loan()
    if loan:
        loan.status = as_status
        loan.closed_on = today()
        if as_status == LOAN_RETURNED and not loan.returned_on:
            loan.returned_on = today()
    return loan


def _cancel_requests(book):
    for req in book.requests.filter(BookRequest.status.in_(ACTIVE_REQUEST_STATUSES)):
        req.status = REQ_CANCELLED
        req.closed_on = today()


def override_status(book, action, member=None):
    """Admin manual override. action: shelf | borrowed | lost | withdrawn."""
    if action == "shelf":
        _close_open_loan(book, LOAN_RETURNED)
        hold = book.requests.filter(BookRequest.status == REQ_ON_HOLD).first()
        if hold:
            # Already held: keep the hold rather than restarting it.
            book.status = ON_HOLD
            db.session.commit()
        else:
            db.session.commit()
            shelve(book)
    elif action == "borrowed":
        if member is None or member.role == "placeholder":
            raise LendingError("Choose the member who has the book.")
        _close_open_loan(book, LOAN_RETURNED)
        db.session.commit()
        return _create_loan(member, book)
    elif action == "lost":
        _close_open_loan(book, LOAN_LOST)
        _cancel_requests(book)
        book.status = LOST
        db.session.commit()
    elif action == "withdrawn":
        _close_open_loan(book, LOAN_RETURNED)
        _cancel_requests(book)
        book.status = WITHDRAWN
        db.session.commit()
    else:
        raise LendingError("Unknown action.")
    return None


def cancel_request(request):
    if request.status not in ACTIVE_REQUEST_STATUSES:
        return
    was_holding = request.status == REQ_ON_HOLD
    request.status = REQ_CANCELLED
    request.closed_on = today()
    db.session.commit()
    if was_holding and request.book.status == ON_HOLD:
        shelve(request.book)


def expire_holds():
    """Daily job: holds not collected in time go back on the shelf. Returns number expired."""
    expired = 0
    now = today()
    holds = BookRequest.query.filter(
        BookRequest.status == REQ_ON_HOLD, BookRequest.hold_until < now
    ).all()
    for req in holds:
        req.status = REQ_EXPIRED
        req.closed_on = now
        if req.book.status == ON_HOLD:
            req.book.status = AVAILABLE
        db.session.commit()
        notify.email_user("hold_expired", req.user, book_title=req.book.title)
        expired += 1
    return expired


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------

def placeholder_user():
    user = User.query.filter_by(role="placeholder").first()
    if user is None:
        user = User(
            name=PLACEHOLDER_NAME,
            address="",
            phone="",
            email=PLACEHOLDER_EMAIL,
            role="placeholder",
            status="closed",
        )
        db.session.add(user)
        db.session.flush()
    return user


def close_account(user):
    if user.loans.filter(Loan.status.in_(OPEN_LOAN_STATUSES)).count():
        raise LendingError(
            "You still have a book out (or one waiting to be checked in). "
            "Your account can be closed once it is all sorted."
        )
    if user.role == "admin" and User.query.filter_by(role="admin").count() <= 1:
        raise LendingError("You're the only librarian, so this account can't be closed.")
    placeholder = placeholder_user()

    for req in user.requests.all():
        if req.status in ACTIVE_REQUEST_STATUSES:
            was_holding = req.status == REQ_ON_HOLD
            req.status = REQ_CANCELLED
            req.closed_on = today()
            if was_holding and req.book.status == ON_HOLD:
                req.book.status = AVAILABLE
        req.user = placeholder
    for loan in user.loans.all():
        loan.user = placeholder
    db.session.flush()
    db.session.delete(user)
    db.session.commit()


def book_for_member(book_id):
    """A book a member is allowed to see (not lost/withdrawn), or None."""
    book = db.session.get(Book, book_id)
    if book is None or not book.is_public:
        return None
    return book
