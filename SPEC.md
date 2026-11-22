# Drumshanbo Traditional Irish Music Library — PoC Specification

**For:** Claude Code
**Goal:** Build a working proof of concept (PoC) that runs on a Windows PC at `localhost`. It must be built so it can later move to a Linux VPS with minimal change.
**Build approach:** Four milestones (section 15). Stop after each milestone so the owner can test it before you continue.

---

## 1. Background

The Drumshanbo Traditional Irish Music Library lends tune books, songbooks and reference books on Irish traditional music to its members. One librarian runs it, often part-time. Members are musicians of all ages; many are not technical and will use the app on their phones.

Members record their own borrows and returns. The app:
- sends escalating email reminders for late books
- lets a member request a book that is out, nudging the current borrower without naming either person
- notifies the librarian of returns and new membership applications by **email and push notification**

---

## 2. Tech stack (fixed — do not substitute)

| Area | Choice |
|---|---|
| Language | Python **3.15** (keep code compatible with 3.12+ in case a dependency lacks 3.15 wheels) |
| Web framework | Flask (app factory + blueprints) |
| Database | SQLite via SQLAlchemy (Flask-SQLAlchemy); Flask-Migrate for schema changes |
| Auth | Flask-Login, Werkzeug password hashing, Flask-WTF (forms + CSRF) |
| Email | `smtplib` / Flask-Mail pointed at **Mailpit** (`localhost:1025`, web UI `localhost:8025`) |
| Push | Web Push with **pywebpush** + VAPID keys (generated once by a CLI command, stored in `.env`) |
| Frontend | Server-rendered Jinja templates, plain CSS, minimal vanilla JS. **PWA:** `manifest.json` + service worker. No SPA framework. |
| ISBN lookup | Open Library API (`https://openlibrary.org/isbn/{isbn}.json`, no key) |
| Scheduled jobs | `flask` CLI commands run daily by **Windows Task Scheduler** (cron later on VPS) |
| Config | `.env` file (python-dotenv); provide `.env.example` |

Run with the Flask dev server on `http://localhost:5000`. `localhost` counts as a secure context, so the service worker and push work in desktop Chrome/Edge.

---

## 3. Roles

- **Public (not logged in):** browse/search catalogue, apply for membership.
- **Member (approved):** borrow, return, request, report lost/damaged, view own books and history, edit own details, close account.
- **Admin / Librarian:** everything in section 9. Multiple admin accounts are allowed; only an existing admin can create another admin. No public admin sign-up.

---

## 4. Membership

### Application form
Fields: **name, address, email, phone number** (all required), password + confirm, tickbox **"I confirm I am 18 or over"** (required), tickbox **consent to data use per the privacy notice** (required, with a link to the notice).

- Adults only. No fees or deposits.
- On submit: status `pending`. The librarian is notified (**email + push**). The applicant gets an email saying "application received".

### Librarian actions
- **Approve:** the member is emailed "you're approved" with a login link.
- **Reject:** optional reason, emailed to the applicant. Rejected applications are deleted automatically after **30 days**.
- **Suspend / reactivate:** suspended members can log in and view their books but cannot borrow or request.

### Login
- Email + password. "Remember me" sessions last **90 days**.
- Forgotten password: emailed reset link (time-limited token, 1 hour).

---

## 5. Catalogue

- About 500 books, **one copy per title** (book = copy; no separate copy table).
- **Fields:** title (required), author/compiler, type (`tune book` / `songbook` / `reference`), ISBN (optional), notes (optional), cover image URL (optional, from ISBN lookup), status.
- **Book status values:** `available`, `on_loan`, `awaiting_check`, `on_hold` (reserved for a requester), `lost`, `withdrawn`.
- `lost` and `withdrawn` books are **hidden from public/member search** but kept in the database and visible to admins.
- The **public catalogue** shows title, author, type, and "Available" or "Out". It **never shows who has a book**.

### Adding books
- Manual add/edit/delete form. Only allow deleting a book with no loan history; otherwise use `withdrawn`.
- **ISBN lookup:** on the add form, the admin types an ISBN and clicks "Look up". The form fills title, author and cover from Open Library. The admin reviews and saves. If not found, show "Not found — enter details manually". Many trad books have no ISBN, so manual entry is normal.
- **Optional extra (only if simple):** a camera barcode scan button using `html5-qrcode`. Skip it if it adds significant complexity.
- **CSV import:** upload a CSV, show a column-mapping step (match CSV headers to fields), preview the first 10 rows, then import. Report rows imported or skipped and why. Include a sample file `sample_data/books_sample.csv`.

---

## 6. Lending rules (editable in admin Settings)

| Rule | Default |
|---|---|
| Loan period | 4 weeks |
| Max books per member at once | 3 |
| Renewals | **None** |
| Borrowing while any book is overdue | **Blocked** |
| Re-borrow same book straight after returning | Allowed unless someone has requested it |
| Hold period for a requester | 7 days |

---

## 7. Member flows

### Home screen (in order)
1. Logo + Irish welcome line: **"Fáilte go Leabharlann Cheoil Dhroim Seanbhó"** (placeholder text, marked TO BE VERIFIED by an Irish speaker; keep it in one config/template string so it's easy to change).
2. **My books**: each with its due date, coloured **green** (OK), **amber** (due within 3 days), **red** (overdue).
3. Big button **Borrow a book**.
4. Big button **Return a book**.
5. Links: **Browse the library**, **My history**, **My details**.

### Borrow (target: 4 taps or fewer)
Search box → results list → tap a book → **confirm screen showing the title in large text** → "Borrow" → success screen with the due date.
Blocked (with a plain-English message) if: the member is suspended, has 3 books out, has an overdue book, or the book is not available / is on hold for someone else.

### Return
"Return a book" lists the member's current books, one tap per book, then a confirm screen that includes an optional **"Any damage? (optional note)"** field.
On confirm:
- Loan → `returned_pending`; book → `awaiting_check`.
- **Overdue reminders stop immediately**, and the book **no longer counts** toward the 3-book limit or the overdue block.
- Librarian notified (**email + push for every return**), with a **"Confirm on shelf"** link/action and a **"Not received"** action. Include the damage note if given.

### Librarian confirms the return
- **Confirm on shelf:** loan closed. If there's an active request, book → `on_hold` and the requester is emailed: *"The book you asked for is back. It's held for you for 7 days."* The hold clock starts **now** (not at the member's tap). Otherwise, book → `available`.
- **Not received:** loan reopened (status `on_loan`, original due date) and the member is emailed politely.

### Request a book that is out
- "Request this book" button on any book that is `on_loan` or `awaiting_check`.
- **Only one active request per book.** If one exists, show: *"Someone has already asked for this book. Check back later."*
- A member cannot request a book they currently have.
- The current borrower is emailed **immediately**: *"Someone is looking for this book. Could you return it as soon as you're finished with it?"* **The email never names the requester, and the requester is never told who has the book.**
- While held, only the requester can borrow it. If not borrowed within 7 days, the hold expires and the book → `available` (handled by the daily job). Email the requester when the hold expires.

### Lost / damaged
- From "My books", a member can tap **"I've lost this book"** (with a confirm step). Loan → `lost_reported`; book → `lost`; librarian emailed. The outcome is decided manually by the librarian; no automatic penalty.
- Damage is reported via the note on return (above).

### My details / leaving
- Edit name, address, phone, email, password.
- **Close my account:** blocked while any book is out. On closing, personal data is deleted and past loans are anonymised (linked to a "former member" placeholder).

### History
- The member's past loans. Loan history older than **2 years** is deleted by the daily job.

---

## 8. Reminder emails (daily job)

Counted from the due date. Each is sent once per loan (record sent stages so nothing is re-sent).

| When | Email | Tone |
|---|---|---|
| 3 days before | Due soon | Friendly heads-up |
| Due date | Due today | Friendly |
| 7 days overdue | 1st overdue | Polite |
| 14 days overdue | 2nd overdue | Firmer; mentions borrowing is blocked until it's returned |
| 28 days overdue | Final notice | Firm; **librarian also emailed** |

After the final notice, no more automatic emails; the loan appears on the admin **Long overdue** list.
- Loans in `returned_pending` get no reminders.
- Emails are signed **"The Drumshanbo Traditional Irish Music Library"**.
- All email wording is stored as editable templates (admin Settings), with placeholders such as `{member_name}`, `{book_title}`, `{due_date}`.

---

## 9. Admin / Librarian area

1. **Dashboard:** counts of pending applications, books out, **awaiting check**, overdue, long overdue, active requests/holds, lost reports.
2. **Applications:** approve / reject (optional reason).
3. **Members:** search; view current books and history; edit details; suspend / reactivate; create admin accounts.
4. **Books:** add/edit/delete, ISBN lookup, CSV import, **manual status override** (mark on shelf, record as borrowed by a chosen member, lost, withdrawn).
5. **Loans:** current, overdue, long overdue, awaiting check (with Confirm / Not received buttons), lost reports.
6. **Settings:** lending rules (section 6), reminder days, email templates, librarian notification email address, list of admins.
7. **Export to CSV:** members, books, loans.
8. **Push setup:** a "Enable notifications on this device" button (subscribes this browser/phone) and a **"Send test push"** button. Support multiple subscribed devices per admin.

---

## 10. Librarian notifications

| Event | Email | Push |
|---|---|---|
| New membership application | ✓ | ✓ |
| Book returned (every return) | ✓ | ✓ |
| Lost book reported | ✓ | — |
| Final overdue notice sent | ✓ | — |

Push notifications open the relevant admin page when tapped. If push sending fails (e.g. an expired subscription), delete that subscription and continue; never let a push failure break the request.

**iPhone note** (put in the README): Web push on iPhone only works if the app has been **added to the Home Screen** (iOS 16.4+) and notifications are enabled from inside the installed app.

---

## 11. Look and feel

- **English only**, apart from the Irish welcome line.
- **Celtic logo:** use a **placeholder simple Celtic knot SVG** at `static/img/logo.svg`; also generate PWA icons (192px, 512px) from it. It must be easy to swap.
- Colours: dark green and cream, high contrast.
- Accessibility: base font size **18px**, sizes in `rem` so phone text-size settings apply, buttons at least 48px tall, text labels on all icons, no swipe-only actions, plain-English messages (no error codes shown to members).
- Mobile-first layout; works on desktop too.

---

## 12. Privacy (GDPR)

- **Privacy notice page** (placeholder text) stating: the data controller is the library; the contact is the librarian; what's collected (name, address, email, phone, loan records), why (running the library and reminders), retention (loan history 2 years; rejected applications 30 days; data deleted on account closure).
- Consent tickbox on the application, with the consent timestamp stored.
- Daily job handles the deletions/anonymisation above.
- Never put personal data in URLs or query strings.

---

## 13. Daily job and CLI commands

- `flask send-reminders`: sends due reminders, expires holds, deletes old history and rejected applications. **One command does all daily work.**
- `flask create-admin`: creates an admin interactively.
- `flask generate-vapid`: generates VAPID keys and prints the lines to paste into `.env`.
- `flask seed`: loads test data (section 14).
- Provide a PowerShell snippet in the README to register `send-reminders` as a daily Windows Task Scheduler task (e.g. 08:00).

---

## 14. Test mode (PoC only — controlled by `TEST_MODE=true` in `.env`)

- A visible **"TEST MODE"** banner on every page.
- **Seed data:** about 500 **invented**, plausible book titles (e.g. "The Leitrim Fiddler's Companion, Vol. 2"); about 15 fake members; loans covering every state: current, due in 3 days, due today, 7/14/28+ days overdue, requested, on hold, awaiting check, lost; 1 pending application; 1 suspended member; 2 admins.
- Login page shortcuts: **"Log in as member"** / **"Log in as librarian"**.
- Admin **"Pretend today is…"** date control. All date logic must use one central `today()` function that respects this override.
- Admin **"Run reminders now"** button (runs the same code as the CLI command).
- **"Send test push"** button.
- All email goes to Mailpit; nothing is sent for real.
- All test features must be completely disabled when `TEST_MODE=false`.

---

## 15. Build milestones (stop after each for testing)

1. **Foundations:** project structure, models, migrations, auth (login, reset password), application → approve flow, book CRUD, ISBN lookup, CSV import, public catalogue, PWA manifest + service worker, seed data, test mode banner and login shortcuts.
2. **Lending:** borrow, return, librarian confirm / not received, all lending-rule checks, My books / history / details, status overrides, lost and damage reporting, close account.
3. **Reminders and requests:** daily command, reminder emails at all stages, request + anonymous nudge, holds and expiry, editable email templates, date override, "Run reminders now", GDPR clean-up.
4. **Notifications and admin extras:** web push (VAPID, subscribe, test push, multi-device), librarian email + push for applications and returns, dashboard counts, CSV exports, Settings page, Task Scheduler instructions.

At the end of each milestone: list what was built, how to test it, and any known gaps.

---

## 16. Out of scope for the PoC

Real email sending (Mailpit only) · hosting, domain, HTTPS, backups · Irish-language interface beyond the welcome line · QR codes on books · request queues · payments, fees, fines · SMS · native app-store apps · statistics beyond CSV export.

---

## 17. Acceptance tests (the PoC is done when all pass)

1. Someone applies → the librarian receives an email (in Mailpit) and a push → approves → the member can log in.
2. A member borrows a book in **4 taps or fewer** on a phone-sized screen (Chrome dev tools mobile view).
3. Moving the "pretend today" date forward and running reminders sends each reminder stage at the right day, once only, with the final notice copied to the librarian.
4. A request sends an anonymous nudge to the borrower; on a confirmed return, the requester is alerted and the 7-day hold works and expires correctly.
5. A return notifies the librarian (email + push); Confirm on shelf and Not received both behave as specified.
6. Suspension, the 3-book limit and the overdue block all prevent borrowing, with clear messages.
7. CSV import of `sample_data/books_sample.csv` works via the column mapping.
8. ISBN lookup fills in details for a known ISBN (e.g. 9780140449136) and fails gracefully for an unknown one.
9. A non-technical person can borrow and return without help.

Also provide **pytest** tests for the lending rules, reminder stages, request/hold logic and the date override.

---

## 18. Deliverables

- Full project in a single folder, with `requirements.txt`, `.env.example`, `README.md`.
- README with step-by-step **PowerShell** setup: install Python 3.15 (`py install 3.15`), create a venv, install requirements, download and run Mailpit, copy `.env.example`, generate VAPID keys, run migrations, seed, run the app, register the Task Scheduler job, and test on a phone via Cloudflare Tunnel (optional).
- A short "Moving to production" section: VPS + gunicorn + nginx + HTTPS, real SMTP relay (e.g. Brevo/Mailjet) with SPF/DKIM, cron instead of Task Scheduler, SQLite backups, `TEST_MODE=false`, real privacy notice, verified Irish text, real logo, real book import.
