"""Editable settings stored in the database, with defaults."""
from flask import current_app

from .extensions import db
from .models import Setting

# Lending rules (spec section 6) and reminder days (section 8).
DEFAULTS = {
    "loan_weeks": "4",
    "max_books": "3",
    "renewals_allowed": "0",
    "block_when_overdue": "1",
    "allow_reborrow": "1",
    "hold_days": "7",
    "remind_due_soon_days": "3",
    "remind_overdue1_days": "7",
    "remind_overdue2_days": "14",
    "remind_final_days": "28",
    "librarian_email": "",
    "pretend_today": "",
}

LABELS = {
    "loan_weeks": "Loan period (weeks)",
    "max_books": "Most books a member can have at once",
    "renewals_allowed": "Renewals allowed per loan (0 = none)",
    "block_when_overdue": "Block borrowing while any book is overdue",
    "allow_reborrow": "Allow re-borrowing the same book straight after returning it",
    "hold_days": "Days a returned book is held for the person who asked for it",
    "remind_due_soon_days": "'Due soon' email: days before the due date",
    "remind_overdue1_days": "1st overdue email: days after the due date",
    "remind_overdue2_days": "2nd overdue email: days after the due date",
    "remind_final_days": "Final notice: days after the due date",
}

INT_KEYS = [
    "loan_weeks",
    "max_books",
    "renewals_allowed",
    "hold_days",
    "remind_due_soon_days",
    "remind_overdue1_days",
    "remind_overdue2_days",
    "remind_final_days",
]
BOOL_KEYS = ["block_when_overdue", "allow_reborrow"]


def get(key):
    row = db.session.get(Setting, key)
    if row is not None:
        return row.value
    if key == "librarian_email":
        return current_app.config["LIBRARIAN_EMAIL"]
    return DEFAULTS.get(key, "")


def get_int(key):
    try:
        return int(get(key))
    except (TypeError, ValueError):
        return int(DEFAULTS[key])


def get_bool(key):
    return str(get(key)) == "1"


def set(key, value):
    row = db.session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=str(value))
        db.session.add(row)
    else:
        row.value = str(value)


def delete(key):
    row = db.session.get(Setting, key)
    if row is not None:
        db.session.delete(row)
