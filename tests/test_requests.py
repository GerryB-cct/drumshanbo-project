from datetime import timedelta

import pytest

from app import lending, reminders
from app.lending import LendingError

from .conftest import START, make_book, make_user, set_today


@pytest.fixture
def setup(app):
    borrower = make_user("Tomás Duignan")
    requester = make_user("Síle O'Rourke")
    book = make_book()
    loan = lending.borrow(borrower, book)
    return borrower, requester, book, loan


def test_request_sends_anonymous_nudge_to_borrower(setup, outbox):
    borrower, requester, book, _loan = setup
    lending.request_book(requester, book)
    assert len(outbox) == 1
    nudge = outbox[0]
    assert nudge.recipients == [borrower.email]
    assert "Someone is looking for this book" in nudge.body
    assert "Síle" not in nudge.body and "Síle" not in nudge.subject
    assert requester.email not in nudge.body


def test_only_one_active_request_per_book(setup):
    _b, requester, book, _l = setup
    lending.request_book(requester, book)
    with pytest.raises(LendingError, match="Someone has already asked for this book. Check back later."):
        lending.request_book(make_user("Third"), book)


def test_cannot_request_own_book(setup):
    borrower, _r, book, _l = setup
    with pytest.raises(LendingError, match="You have this book"):
        lending.request_book(borrower, book)


def test_cannot_request_available_book(app):
    with pytest.raises(LendingError, match="borrow it now"):
        lending.request_book(make_user(), make_book())


def test_can_request_book_awaiting_check(setup, outbox, pushes):
    borrower, requester, book, loan = setup
    lending.return_book(borrower, loan)
    outbox.clear()
    lending.request_book(requester, book)
    assert outbox == []  # borrower already returned it, so no nudge


def test_confirmed_return_puts_book_on_hold_and_emails_requester(setup, outbox, pushes):
    borrower, requester, book, loan = setup
    lending.request_book(requester, book)
    set_today(START + timedelta(days=5))
    lending.return_book(borrower, loan)
    set_today(START + timedelta(days=8))  # librarian confirms 3 days later
    lending.confirm_on_shelf(loan)
    req = book.active_request()
    assert book.status == "on_hold"
    assert req.status == "on_hold"
    # The hold clock starts when the librarian confirms, not when the member tapped return.
    assert req.hold_started_on == START + timedelta(days=8)
    assert req.hold_until == START + timedelta(days=15)
    held_mail = outbox[-1]
    assert held_mail.recipients == [requester.email]
    assert "It's held for you for 7 days" in held_mail.body
    assert "Tomás" not in held_mail.body


def test_only_requester_can_borrow_held_book(setup, outbox, pushes):
    borrower, requester, book, loan = setup
    lending.request_book(requester, book)
    lending.return_book(borrower, loan)
    lending.confirm_on_shelf(loan)
    with pytest.raises(LendingError, match="being held"):
        lending.borrow(make_user("Someone Else"), book)
    with pytest.raises(LendingError, match="being held"):
        lending.borrow(borrower, book)
    new_loan = lending.borrow(requester, book)
    assert new_loan.user_id == requester.id
    assert book.active_request() is None


def test_hold_expires_after_seven_days(setup, outbox, pushes):
    borrower, requester, book, loan = setup
    lending.request_book(requester, book)
    lending.return_book(borrower, loan)
    lending.confirm_on_shelf(loan)  # hold START .. START+7
    set_today(START + timedelta(days=7))
    assert reminders.run_daily()["holds_expired"] == 0
    assert book.status == "on_hold"
    set_today(START + timedelta(days=8))
    assert reminders.run_daily()["holds_expired"] == 1
    assert book.status == "available"
    assert outbox[-1].recipients == [requester.email]
    assert "hold has now ended" in outbox[-1].body
    lending.borrow(make_user("Anyone"), book)


def test_new_request_allowed_after_previous_fulfilled(setup, outbox, pushes):
    borrower, requester, book, loan = setup
    lending.request_book(requester, book)
    lending.return_book(borrower, loan)
    lending.confirm_on_shelf(loan)
    lending.borrow(requester, book)
    lending.request_book(borrower, book)  # fine now
