from datetime import timedelta

import pytest

from app import lending, settings
from app.extensions import db
from app.lending import LendingError
from app.models import Loan, User

from .conftest import START, make_book, make_user, set_today


def test_borrow_sets_due_date_four_weeks_ahead(app):
    user, book = make_user(), make_book()
    loan = lending.borrow(user, book)
    assert loan.due_on == START + timedelta(weeks=4)
    assert book.status == "on_loan"


def test_loan_period_setting_is_used(app):
    settings.set("loan_weeks", "2")
    db.session.commit()
    loan = lending.borrow(make_user(), make_book())
    assert loan.due_on == START + timedelta(weeks=2)


def test_three_book_limit(app):
    user = make_user()
    for i in range(3):
        lending.borrow(user, make_book(f"Book {i}"))
    with pytest.raises(LendingError, match="3 books out"):
        lending.borrow(user, make_book("Book 4"))


def test_overdue_book_blocks_borrowing(app):
    user = make_user()
    lending.borrow(user, make_book("Old"))
    set_today(START + timedelta(weeks=4, days=1))
    with pytest.raises(LendingError, match="overdue"):
        lending.borrow(user, make_book("New"))


def test_overdue_block_can_be_switched_off(app):
    user = make_user()
    lending.borrow(user, make_book("Old"))
    set_today(START + timedelta(weeks=5))
    settings.set("block_when_overdue", "0")
    db.session.commit()
    lending.borrow(user, make_book("New"))


def test_suspended_member_cannot_borrow_or_request(app):
    user = make_user(status="suspended")
    with pytest.raises(LendingError, match="paused"):
        lending.borrow(user, make_book())
    other = make_user("Other")
    book = make_book("Out")
    lending.borrow(other, book)
    with pytest.raises(LendingError, match="paused"):
        lending.request_book(user, book)


def test_book_not_available(app):
    book = make_book()
    lending.borrow(make_user("A"), book)
    with pytest.raises(LendingError, match="isn't on the shelf"):
        lending.borrow(make_user("B"), book)


def test_returned_pending_does_not_count_towards_limit_or_overdue(app, outbox, pushes):
    user = make_user()
    loans = [lending.borrow(user, make_book(f"Book {i}")) for i in range(3)]
    set_today(START + timedelta(weeks=6))  # all overdue
    for loan in loans:
        lending.return_book(user, loan)
    lending.borrow(user, make_book("Fresh"))  # neither limit nor overdue applies now


def test_return_notifies_librarian_by_email_and_push(app, outbox, pushes):
    user, book = make_user("Seán Kelly"), make_book()
    loan = lending.borrow(user, book)
    lending.return_book(user, loan, "Page 3 torn")
    assert loan.status == "returned_pending"
    assert book.status == "awaiting_check"
    assert len(pushes) == 1
    librarian_mail = [m for m in outbox if "librarian@example.com" in m.recipients]
    assert len(librarian_mail) == 1
    assert "Page 3 torn" in librarian_mail[0].body
    assert "Seán Kelly" in librarian_mail[0].body
    assert f"/admin/loans/{loan.id}/check" in librarian_mail[0].body


def test_confirm_on_shelf_without_request_makes_book_available(app, outbox, pushes):
    user, book = make_user(), make_book()
    loan = lending.borrow(user, book)
    lending.return_book(user, loan)
    lending.confirm_on_shelf(loan)
    assert loan.status == "returned"
    assert book.status == "available"


def test_not_received_reopens_loan_with_original_due_date(app, outbox, pushes):
    user, book = make_user(), make_book()
    loan = lending.borrow(user, book)
    due = loan.due_on
    set_today(START + timedelta(days=10))
    lending.return_book(user, loan)
    lending.not_received(loan)
    assert loan.status == "on_loan"
    assert loan.due_on == due
    assert book.status == "on_loan"
    assert outbox[-1].recipients == [user.email]
    assert "couldn't find" in outbox[-1].subject


def test_reborrow_allowed_by_default(app, outbox, pushes):
    user, book = make_user(), make_book()
    loan = lending.borrow(user, book)
    lending.return_book(user, loan)
    lending.confirm_on_shelf(loan)
    lending.borrow(user, book)


def test_reborrow_can_be_switched_off(app, outbox, pushes):
    settings.set("allow_reborrow", "0")
    db.session.commit()
    user, book = make_user(), make_book()
    loan = lending.borrow(user, book)
    lending.return_book(user, loan)
    lending.confirm_on_shelf(loan)
    with pytest.raises(LendingError, match="just returned"):
        lending.borrow(user, book)


def test_no_renewals_by_default(app):
    user = make_user()
    loan = lending.borrow(user, make_book())
    with pytest.raises(LendingError, match="Renewals aren't available"):
        lending.renew(user, loan)


def test_report_lost(app, outbox):
    user, book = make_user(), make_book()
    loan = lending.borrow(user, book)
    lending.report_lost(user, loan)
    assert loan.status == "lost_reported"
    assert book.status == "lost"
    assert outbox[-1].recipients == ["librarian@example.com"]


def test_close_account_blocked_with_book_out(app):
    user = make_user()
    lending.borrow(user, make_book())
    with pytest.raises(LendingError, match="still have a book"):
        lending.close_account(user)


def test_close_account_deletes_personal_data_and_anonymises_loans(app, outbox, pushes):
    user, book = make_user("Bríd Flynn", email="brid@example.com"), make_book()
    loan = lending.borrow(user, book)
    lending.return_book(user, loan)
    lending.confirm_on_shelf(loan)
    loan_id = loan.id
    lending.close_account(user)
    assert User.query.filter_by(email="brid@example.com").first() is None
    kept = db.session.get(Loan, loan_id)
    assert kept.user.role == "placeholder"
    assert kept.user.name == "Former member"


def test_admin_override_borrowed_by_member(app):
    member, book = make_user(), make_book()
    lending.override_status(book, "borrowed", member)
    assert book.status == "on_loan"
    assert book.open_loan().user_id == member.id


def test_admin_override_withdrawn_hides_book(app):
    book = make_book()
    lending.override_status(book, "withdrawn")
    assert book.status == "withdrawn"
    assert lending.book_for_member(book.id) is None
