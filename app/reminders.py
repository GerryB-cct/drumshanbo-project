"""The daily job. `flask send-reminders` and the admin "Run reminders now" button both call run_daily()."""
from . import lending, notify, settings
from .dates import add_days, nice_date, today
from .extensions import db
from .models import (
    LOAN_LOST,
    LOAN_ON_LOAN,
    LOAN_RETURNED,
    REQ_CANCELLED,
    REQ_EXPIRED,
    REQ_FULFILLED,
    BookRequest,
    Loan,
    ReminderLog,
    User,
)

HISTORY_KEEP_DAYS = 730  # 2 years
REJECTED_KEEP_DAYS = 30

STAGE_LABELS = {
    "due_soon": "Due soon",
    "due_today": "Due today",
    "overdue_1": "1st overdue",
    "overdue_2": "2nd overdue",
    "final_notice": "Final notice",
}


def stage_windows():
    """[(stage, from_day, until_day)] in days after the due date (negative = before).

    A stage is sent when days-after-due falls in [from_day, until_day). The window means
    a missed run catches up the next day, but a stage is never sent once the next stage
    has been reached, so members never get a stale "due soon" after the due date.
    """
    soon = -settings.get_int("remind_due_soon_days")
    o1 = settings.get_int("remind_overdue1_days")
    o2 = settings.get_int("remind_overdue2_days")
    final = settings.get_int("remind_final_days")
    return [
        ("due_soon", soon, 0),
        ("due_today", 0, 1),
        ("overdue_1", o1, o2),
        ("overdue_2", o2, final),
        ("final_notice", final, None),
    ]


def stage_due(loan, on_date):
    days = loan.days_overdue(on_date)
    sent = loan.stages_sent()
    for stage, start, end in stage_windows():
        if days >= start and (end is None or days < end) and stage not in sent:
            return stage
    return None


def long_overdue_cutoff(on_date=None):
    return add_days(on_date or today(), -settings.get_int("remind_final_days"))


def send_reminders():
    now = today()
    counts = {stage: 0 for stage in STAGE_LABELS}
    loans = Loan.query.filter(Loan.status == LOAN_ON_LOAN).all()  # returned_pending gets nothing
    for loan in loans:
        stage = stage_due(loan, now)
        if not stage:
            continue
        days = loan.days_overdue(now)
        context = dict(
            book_title=loan.book.title,
            due_date=nice_date(loan.due_on),
            days_overdue=days,
            link=notify.external_url("main.home"),
        )
        # Record first so a crash part-way can never cause a double send.
        db.session.add(ReminderLog(loan=loan, stage=stage, sent_on=now))
        db.session.commit()
        notify.email_user(stage, loan.user, **context)
        if stage == "final_notice":
            context["link"] = notify.external_url("admin.loans", view="long")
            notify.email_librarian("librarian_final_notice", member_name=loan.user.name, **context)
        counts[stage] += 1
    return counts


def clean_up():
    """GDPR retention: loan history > 2 years, rejected applications > 30 days."""
    now = today()
    history_cutoff = add_days(now, -HISTORY_KEEP_DAYS)
    old_loans = Loan.query.filter(
        Loan.status.in_([LOAN_RETURNED, LOAN_LOST]), Loan.closed_on < history_cutoff
    ).all()
    for loan in old_loans:
        db.session.delete(loan)

    old_requests = BookRequest.query.filter(
        BookRequest.status.in_([REQ_FULFILLED, REQ_EXPIRED, REQ_CANCELLED]),
        BookRequest.closed_on < history_cutoff,
    ).all()
    for req in old_requests:
        db.session.delete(req)

    rejected_cutoff = add_days(now, -REJECTED_KEEP_DAYS)
    rejected = User.query.filter(
        User.status == "rejected", User.rejected_on < rejected_cutoff
    ).all()
    for user in rejected:
        db.session.delete(user)
    db.session.commit()
    return {
        "loans_deleted": len(old_loans),
        "requests_deleted": len(old_requests),
        "applications_deleted": len(rejected),
    }


def run_daily():
    summary = {"date": today()}
    summary["reminders"] = send_reminders()
    summary["holds_expired"] = lending.expire_holds()
    summary.update(clean_up())
    return summary


def summary_lines(summary):
    lines = [f"Daily job for {nice_date(summary['date'])}:"]
    for stage, n in summary["reminders"].items():
        lines.append(f"  {STAGE_LABELS[stage]} emails sent: {n}")
    lines.append(f"  Holds expired: {summary['holds_expired']}")
    lines.append(f"  Old loan records deleted: {summary['loans_deleted']}")
    lines.append(f"  Old request records deleted: {summary['requests_deleted']}")
    lines.append(f"  Rejected applications deleted: {summary['applications_deleted']}")
    return lines
