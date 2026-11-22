from datetime import timedelta

import pytest

from app import lending, reminders
from app.models import User

from .conftest import START, make_book, make_user, set_today

DUE = START + timedelta(weeks=4)


@pytest.fixture
def loan(app):
    user = make_user("Niamh Reynolds")
    return lending.borrow(user, make_book())


def run_on(day_offset):
    set_today(DUE + timedelta(days=day_offset))
    return reminders.run_daily()["reminders"]


def member_subjects(outbox, email):
    return [m.subject for m in outbox if m.recipients == [email]]


EXPECTED = {
    -3: "due_soon",
    0: "due_today",
    7: "overdue_1",
    14: "overdue_2",
    28: "final_notice",
}


def test_each_stage_sent_on_the_right_day_once_only(loan, outbox):
    for offset in range(-6, 40):
        counts = run_on(offset)
        sent = [stage for stage, n in counts.items() if n]
        if offset in EXPECTED:
            assert sent == [EXPECTED[offset]], f"day {offset}"
        else:
            assert sent == [], f"day {offset}"
        # Running twice on the same day never re-sends.
        assert not any(reminders.send_reminders().values())
    assert loan.stages_sent() == set(EXPECTED.values())
    assert len(member_subjects(outbox, loan.user.email)) == 5


def test_final_notice_copied_to_librarian(loan, outbox):
    run_on(28)
    to_librarian = [m for m in outbox if m.recipients == ["librarian@example.com"]]
    assert len(to_librarian) == 1
    assert "Final notice sent" in to_librarian[0].subject
    assert "Niamh Reynolds" in to_librarian[0].body


def test_second_overdue_mentions_borrowing_blocked(loan, outbox):
    run_on(14)
    assert "not be able to borrow" in outbox[-1].body


def test_emails_signed_by_library(loan, outbox):
    run_on(-3)
    assert outbox[-1].body.rstrip().endswith("The Drumshanbo Traditional Irish Music Library")


def test_returned_pending_gets_no_reminders(loan, outbox, pushes):
    set_today(DUE - timedelta(days=5))
    lending.return_book(loan.user, loan)
    outbox.clear()
    for offset in (-3, 0, 7, 14, 28):
        assert not any(run_on(offset).values())
    assert member_subjects(outbox, loan.user.email) == []


def test_missed_days_do_not_send_stale_stages(loan, outbox):
    # Nobody ran the job until 30 days overdue: only the final notice goes, not all five.
    counts = run_on(30)
    assert [s for s, n in counts.items() if n] == ["final_notice"]
    assert len(member_subjects(outbox, loan.user.email)) == 1


def test_job_catches_up_within_a_stage_window(loan, outbox):
    # Job didn't run on day 7; it runs on day 9 and still sends the 1st overdue.
    assert [s for s, n in run_on(9).items() if n] == ["overdue_1"]


def test_long_overdue_cutoff(loan):
    set_today(DUE + timedelta(days=28))
    assert loan.due_on <= reminders.long_overdue_cutoff()


def test_template_edits_are_used(loan, outbox):
    from app import settings
    from app.extensions import db

    settings.set("email:due_soon:subject", "Custom: {book_title} due {due_date}")
    db.session.commit()
    run_on(-3)
    assert outbox[-1].subject.startswith("Custom: The Leitrim Fiddler's Companion")


def test_rejected_applications_deleted_after_30_days(app):
    user = User(name="Rejected", email="r@example.com", status="rejected", rejected_on=START,
                address="", phone="")
    from app.extensions import db

    db.session.add(user)
    db.session.commit()
    set_today(START + timedelta(days=30))
    assert reminders.clean_up()["applications_deleted"] == 0
    set_today(START + timedelta(days=31))
    assert reminders.clean_up()["applications_deleted"] == 1


def test_loan_history_deleted_after_two_years(app, outbox, pushes):
    user, book = make_user(), make_book()
    loan = lending.borrow(user, book)
    lending.return_book(user, loan)
    lending.confirm_on_shelf(loan)
    set_today(START + timedelta(days=730))
    assert reminders.clean_up()["loans_deleted"] == 0
    set_today(START + timedelta(days=731))
    assert reminders.clean_up()["loans_deleted"] == 1
