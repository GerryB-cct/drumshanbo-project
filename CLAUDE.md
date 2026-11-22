# CLAUDE.md

Context for Claude Code sessions on this project.

## What this is
Proof of concept for the Drumshanbo Traditional Irish Music Library lending app. `SPEC.md` is the
source of truth. `README.md` has setup, testing and known gaps. `LOG.md` is the session diary
(newest first). When the owner says "wrap up", update LOG.md and README.md.

## Fixed stack (don't substitute)
Python 3.15 (keep 3.12-compatible), Flask app factory + blueprints, Flask-SQLAlchemy on SQLite,
Flask-Migrate, Flask-Login, Flask-WTF, Flask-Mail → Mailpit, pywebpush + VAPID, Jinja + plain CSS +
vanilla JS, PWA. No SPA framework.

## Rules that matter
- **All dates go through `app/dates.py: today()`**, never `date.today()`. It respects the TEST_MODE "pretend today".
- **All status changes go through `app/lending.py`.** Views don't set `book.status` / `loan.status` directly.
- Every TEST_MODE feature must be disabled when `TEST_MODE=false` (use `@test_mode_required`).
- Never put personal data in URLs or query strings (member search is POST; the reset token holds only an id + hash fingerprint).
- The public catalogue and the nudge email must never reveal who has a book or who asked for it.
- Email and push failures are logged, never raised (`app/notify.py`).
- Member-facing messages are plain English, with no error codes.
- Email wording lives in `app/email_templates.py` (defaults). Admin edits are stored in the `settings` table.
- After changing models: `flask db migrate -m "..."` then `flask db upgrade` (batch mode is on for SQLite).

## Commands
```
.venv\Scripts\python -m pytest        # tests
.venv\Scripts\flask run --debug       # app on :5000
tools\mailpit.exe                     # mail inbox on :8025, SMTP :1025
.venv\Scripts\flask seed --yes        # reset test data
.venv\Scripts\flask send-reminders    # daily job
```
