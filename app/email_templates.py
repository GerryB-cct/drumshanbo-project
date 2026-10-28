"""Default wording for every email. Admins can edit these in Settings > Email wording.

Placeholders in curly brackets are filled in when the email is sent, e.g.
{member_name}, {book_title}, {due_date}, {link}. Unknown placeholders are left as they are.
"""
from . import settings

SIGNATURE = "The Drumshanbo Traditional Irish Music Library"

TEMPLATES = {
    # --- Membership --------------------------------------------------------
    "application_received": {
        "label": "Application received (to applicant)",
        "placeholders": ["member_name"],
        "subject": "We have received your membership application",
        "body": (
            "Dear {member_name},\n\n"
            "Thank you for applying to join the library. The librarian will look at your "
            "application soon and we will email you as soon as it has been approved.\n\n"
            "{signature}"
        ),
    },
    "application_approved": {
        "label": "Application approved (to member)",
        "placeholders": ["member_name", "link"],
        "subject": "Welcome! Your library membership is approved",
        "body": (
            "Dear {member_name},\n\n"
            "Good news: your membership has been approved. You can now log in and borrow books:\n\n"
            "{link}\n\n"
            "Log in with the email address and password you chose when you applied.\n\n"
            "{signature}"
        ),
    },
    "application_rejected": {
        "label": "Application not approved (to applicant)",
        "placeholders": ["member_name", "reason"],
        "subject": "About your library membership application",
        "body": (
            "Dear {member_name},\n\n"
            "Thank you for your interest in the library. Unfortunately we are not able to "
            "approve your application at this time.\n\n"
            "{reason}\n\n"
            "If you have any questions, please reply to this email.\n\n"
            "{signature}"
        ),
    },
    "password_reset": {
        "label": "Password reset link",
        "placeholders": ["member_name", "link"],
        "subject": "Reset your library password",
        "body": (
            "Dear {member_name},\n\n"
            "Someone (hopefully you) asked to reset your password. Use this link within the "
            "next hour to choose a new one:\n\n"
            "{link}\n\n"
            "If you did not ask for this, you can ignore this email.\n\n"
            "{signature}"
        ),
    },
    # --- Reminders ---------------------------------------------------------
    "due_soon": {
        "label": "Reminder: due soon",
        "placeholders": ["member_name", "book_title", "due_date", "link"],
        "subject": "Friendly reminder: \"{book_title}\" is due back soon",
        "body": (
            "Dear {member_name},\n\n"
            "Just a friendly heads-up: \"{book_title}\" is due back on {due_date}.\n\n"
            "When you bring it back, tap \"Return a book\" in the app:\n{link}\n\n"
            "Thank you, and happy playing!\n\n"
            "{signature}"
        ),
    },
    "due_today": {
        "label": "Reminder: due today",
        "placeholders": ["member_name", "book_title", "due_date", "link"],
        "subject": "\"{book_title}\" is due back today",
        "body": (
            "Dear {member_name},\n\n"
            "\"{book_title}\" is due back today ({due_date}). If you have already returned it, "
            "thank you! If not, please bring it back when you can and tap \"Return a book\" in the app:\n{link}\n\n"
            "{signature}"
        ),
    },
    "overdue_1": {
        "label": "1st overdue notice",
        "placeholders": ["member_name", "book_title", "due_date", "days_overdue", "link"],
        "subject": "\"{book_title}\" is now overdue",
        "body": (
            "Dear {member_name},\n\n"
            "Our records show that \"{book_title}\" was due back on {due_date} and is now "
            "{days_overdue} days overdue. Could you please return it as soon as possible?\n\n"
            "When you return it, tap \"Return a book\" in the app:\n{link}\n\n"
            "{signature}"
        ),
    },
    "overdue_2": {
        "label": "2nd overdue notice",
        "placeholders": ["member_name", "book_title", "due_date", "days_overdue", "link"],
        "subject": "Second notice: please return \"{book_title}\"",
        "body": (
            "Dear {member_name},\n\n"
            "\"{book_title}\" was due back on {due_date} and is now {days_overdue} days overdue.\n\n"
            "Please return it straight away. You will not be able to borrow any other books "
            "until it has been returned.\n\n"
            "When you return it, tap \"Return a book\" in the app:\n{link}\n\n"
            "{signature}"
        ),
    },
    "final_notice": {
        "label": "Final notice (to member)",
        "placeholders": ["member_name", "book_title", "due_date", "days_overdue", "link"],
        "subject": "Final notice: \"{book_title}\" must be returned",
        "body": (
            "Dear {member_name},\n\n"
            "This is our final notice about \"{book_title}\", which was due back on {due_date} "
            "and is now {days_overdue} days overdue.\n\n"
            "Please return it now. Borrowing stays blocked until it is back. The librarian has "
            "been told and may contact you directly.\n\n"
            "If you have lost the book, please let us know using \"I've lost this book\" in the app:\n{link}\n\n"
            "{signature}"
        ),
    },
    # --- Requests and holds ------------------------------------------------
    "nudge_borrower": {
        "label": "Someone is looking for your book (to borrower)",
        "placeholders": ["member_name", "book_title", "due_date"],
        "subject": "Someone is looking for \"{book_title}\"",
        "body": (
            "Dear {member_name},\n\n"
            "Someone is looking for this book: \"{book_title}\". Could you return it as soon "
            "as you're finished with it?\n\n"
            "There's no rush before your due date ({due_date}), but an early return would be "
            "much appreciated.\n\n"
            "{signature}"
        ),
    },
    "hold_ready": {
        "label": "Requested book is back and held (to requester)",
        "placeholders": ["member_name", "book_title", "hold_days", "hold_until", "link"],
        "subject": "\"{book_title}\" is back and held for you",
        "body": (
            "Dear {member_name},\n\n"
            "The book you asked for is back. It's held for you for {hold_days} days.\n\n"
            "\"{book_title}\" is held for you until {hold_until}. Borrow it in the app:\n{link}\n\n"
            "{signature}"
        ),
    },
    "hold_expired": {
        "label": "Hold has expired (to requester)",
        "placeholders": ["member_name", "book_title"],
        "subject": "Your hold on \"{book_title}\" has ended",
        "body": (
            "Dear {member_name},\n\n"
            "\"{book_title}\" was held for you, but the hold has now ended and the book is "
            "back on the shelf for everyone. If it's still there, you're welcome to borrow it.\n\n"
            "{signature}"
        ),
    },
    # --- Returns -----------------------------------------------------------
    "not_received": {
        "label": "Return not received (to member)",
        "placeholders": ["member_name", "book_title", "due_date"],
        "subject": "We couldn't find \"{book_title}\" on the shelf",
        "body": (
            "Dear {member_name},\n\n"
            "Thank you for marking \"{book_title}\" as returned. Unfortunately the librarian "
            "could not find it in the library, so it is still showing as on loan to you "
            "(due {due_date}).\n\n"
            "It may simply have been mislaid. Could you check at home, or reply to this email "
            "if you're sure you returned it? Thank you.\n\n"
            "{signature}"
        ),
    },
    # --- To the librarian --------------------------------------------------
    "librarian_new_application": {
        "label": "Librarian: new membership application",
        "placeholders": ["applicant_name", "link"],
        "subject": "New membership application: {applicant_name}",
        "body": (
            "A new membership application has arrived from {applicant_name}.\n\n"
            "Review it here:\n{link}\n"
        ),
    },
    "librarian_return": {
        "label": "Librarian: book returned",
        "placeholders": ["member_name", "book_title", "damage_note", "link"],
        "subject": "Returned: \"{book_title}\"",
        "body": (
            "{member_name} has marked \"{book_title}\" as returned.\n\n"
            "Damage note: {damage_note}\n\n"
            "Please check the shelf, then choose \"Confirm on shelf\" or \"Not received\":\n{link}\n"
        ),
    },
    "librarian_lost": {
        "label": "Librarian: book reported lost",
        "placeholders": ["member_name", "book_title", "link"],
        "subject": "Lost book reported: \"{book_title}\"",
        "body": (
            "{member_name} has reported \"{book_title}\" as lost.\n\n"
            "Decide what to do here:\n{link}\n"
        ),
    },
    "librarian_final_notice": {
        "label": "Librarian: final overdue notice sent",
        "placeholders": ["member_name", "book_title", "due_date", "days_overdue", "link"],
        "subject": "Final notice sent: \"{book_title}\"",
        "body": (
            "A final overdue notice has been sent to {member_name} for \"{book_title}\" "
            "(due {due_date}, {days_overdue} days overdue).\n\n"
            "No more automatic emails will be sent. The loan is now on the Long overdue list:\n{link}\n"
        ),
    },
}


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _fill(text, context):
    try:
        return text.format_map(_SafeDict(context))
    except (ValueError, IndexError, AttributeError):
        return text


def get_template(name):
    default = TEMPLATES[name]
    subject = settings.get(f"email:{name}:subject") or default["subject"]
    body = settings.get(f"email:{name}:body") or default["body"]
    return subject, body


def render(name, **context):
    context.setdefault("signature", SIGNATURE)
    subject, body = get_template(name)
    return _fill(subject, context), _fill(body, context)
