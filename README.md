# Drumshanbo Traditional Irish Music Library: proof of concept

A small web app for lending tune books, songbooks and reference books. Members borrow and return
from their phones. The librarian gets an email and a push notification for every return and new
application. The app sends overdue reminders automatically.

Built with Python 3.15 and Flask, using SQLite, Jinja templates and plain CSS/JS. It is a PWA, so
it can be installed and receive push notifications. It runs on a Windows PC at `http://localhost:5000`
and is ready to move to a Linux VPS later (see [Moving to production](#moving-to-production)).

- Spec: `SPEC.md` (copy of the original specification)
- Session diary: [LOG.md](LOG.md)
- Reports: [28 Oct 2026: PoC built](reports/2026-10-28-session-report.md)

---

## 1. Setup on Windows (PowerShell)

Run each block in PowerShell from the project folder:

```powershell
cd "C:\Users\VelzyG\Documents\lowcode-project\drumshanbo-project"
```

### 1.1 Install Python 3.15
```powershell
py install 3.15          # Python install manager (skip if `py -3.15 --version` already works)
py -3.15 --version
```

### 1.2 Create a virtual environment and install the requirements
```powershell
py -3.15 -m venv .venv
.\.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install --upgrade pip
pip install -r requirements.txt
```
The code also runs on Python 3.12+ if a dependency ever lacks a 3.15 wheel.

### 1.3 Download and run Mailpit (catches all email; nothing is really sent)
`tools\mailpit.exe` is already included in this copy. To download it fresh:
```powershell
New-Item -ItemType Directory -Force tools | Out-Null
Invoke-WebRequest https://github.com/axllent/mailpit/releases/latest/download/mailpit-windows-amd64.zip -OutFile tools\mailpit.zip
Expand-Archive tools\mailpit.zip -DestinationPath tools -Force
Remove-Item tools\mailpit.zip
```
Run it in its own PowerShell window and leave it running:
```powershell
.\tools\mailpit.exe
```
The inbox is at **http://localhost:8025**. The app sends to SMTP `localhost:1025`.

### 1.4 Create `.env`
```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste the output as SECRET_KEY in .env
```

### 1.5 Generate push (VAPID) keys
```powershell
flask generate-vapid
```
Paste the two printed lines (`VAPID_PUBLIC_KEY=…`, `VAPID_PRIVATE_KEY=…`) into `.env`.

### 1.6 Create the database and load test data
```powershell
flask db upgrade          # creates instance\library.db from the migrations
flask seed                # TEST_MODE only: wipes everything and loads test data
```

### 1.7 Run the app
```powershell
flask run --debug
```
Open **http://localhost:5000**. On the login page, use **Log in as member** or **Log in as librarian**.

### 1.8 Run the tests
```powershell
python -m pytest
```

---

## 2. Test accounts (after `flask seed`)

Every account's password is `password`.

| Account | Situation |
|---|---|
| `member@example.com` (Mary Test) | Demo member: one green and one amber loan, and a book held for her |
| `librarian@example.com`, `admin2@example.com` | Librarians (admins) |
| `liam.cryan@example.com` | Suspended |
| `grainne.mckiernan@example.com` | 3 books out (at the limit) |
| `padraig.moran@example.com` | 7 days overdue, so borrowing is blocked |
| `sean.kelly@example.com` | Due in 3 days |
| `aoife.gallagher@example.com` | Due today |
| `niamh.reynolds@example.com` / `ciaran.mcdermott@example.com` / `brid.flynn@example.com` | 14 / 28 / 40 days overdue |
| `tomas.duignan@example.com` | Has a book that `sile.orourke@example.com` has requested |
| `declan.mulvey@example.com` | Returned a book with a damage note; it's awaiting check |
| `orla.gaffney@example.com` | Reported a book lost |
| `eoin.rynn@example.com` | Has a hold that expires in 2 days |
| Caoimhe Byrne | Pending application |

The seed also adds 500 invented books, past loan history (some over 2 years old, which the daily
job deletes) and a rejected application from 35 days ago (also deleted by the daily job).

---

## 3. Test mode

`TEST_MODE=true` in `.env` turns on:
- a red **TEST MODE** banner on every page
- **Log in as member / librarian** buttons on the login page
- on the librarian dashboard: **Pretend today is…** (plus +1/+3/+7/+14 day buttons), **Run reminders now** and **Send test push**
- `flask seed`

All date logic goes through one function, `app/dates.py: today()`, which follows the pretend date.
With `TEST_MODE=false`, every one of these features is switched off: the routes return "not found"
and the pretend date is ignored.

---

## 4. Walking through the acceptance tests

| # | How to test |
|---|---|
| 1 | Log out. **Join**, fill in the form. Mailpit shows "application received" (to the applicant) and "New membership application" (to the librarian). A push arrives if you've enabled it (see 6). Log in as librarian → **Applications** → **Approve**. The applicant gets "approved" and can log in. |
| 2 | Chrome DevTools → device toolbar (phone size). Log in as member. Tap **Borrow a book** (1) → type "Leitrim" and press Search (2) → tap a book (3) → **Borrow** (4). The success screen shows the due date. |
| 3 | As librarian: **Run reminders now**. Mailpit shows one email per stage for the seeded loans. Run it again and nothing new is sent. Use **+1 day** / **+7 days** and run again to watch the next stages go out. The final notice is also copied to the librarian. Loans past the final notice show under **Loans → Long overdue**. |
| 4 | As `sile.orourke` (or any member), open a book that's out → **Request this book**. The borrower gets "Someone is looking for…", which never names the requester. When it's returned and the librarian taps **Confirm on shelf**, the requester gets "It's held for you for 7 days" and only they can borrow it. Move the date +8 days and **Run reminders now**: the hold expires, the book becomes available and the requester is emailed. |
| 5 | As member: **Return a book** → tap a book → add a damage note → confirm. The librarian gets an email (and a push) with a link. **Loans → Awaiting check**: **Confirm on shelf** makes the book available (or held). **Not received** puts it back on the member's account with the original due date and emails them. |
| 6 | Log in as `liam.cryan` (suspended), `grainne.mckiernan` (3 books) or `padraig.moran` (overdue) and try to borrow. Each gets a plain-English message. |
| 7 | **Books → Import from CSV** → upload `sample_data/books_sample.csv`. Columns are matched automatically ("Book Title" → Title, etc.) and the first 10 rows are previewed. Import gives 21 imported and 4 skipped (no title, unknown type, bad ISBN, duplicate), each with its reason. |
| 8 | **Books → Add a book** → ISBN `9780140449136` → **Look up** fills the title, author and cover. `9798765432104` shows "Not found — enter details manually". **Scan barcode with camera** works in Chrome/Edge on localhost or HTTPS. |
| 9 | Hand a phone to someone and ask them to borrow, then return, a book. |

### Push notifications
Librarian → **Notifications** → **Enable notifications on this device** → allow → **Send test push**.
Each admin can subscribe several devices. Tapping a notification opens the relevant admin page.
Subscriptions that fail (e.g. expired) are deleted automatically, and a failed push never breaks
the page that triggered it.

> **iPhone note:** web push on iPhone only works if the app has been **added to the Home Screen**
> (iOS 16.4 or later) and notifications are enabled **from inside the installed app**.
> In Safari: Share → Add to Home Screen, open the app from its icon, then go to Notifications → Enable.

---

## 5. Daily job (Windows Task Scheduler)

`flask send-reminders` does all the daily work: reminder emails, hold expiry, and deleting loan
history over 2 years old and rejected applications over 30 days old. `scripts\daily_job.ps1` runs it
and appends the output to `instance\daily-job.log`.

Register it to run every day at 08:00. Run PowerShell from the project folder:
```powershell
$project = (Get-Location).Path
$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
           -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$project\scripts\daily_job.ps1`"" `
           -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Daily -At 08:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable    # catch up if the PC was off at 08:00
Register-ScheduledTask -TaskName "Drumshanbo Library daily job" -Action $action -Trigger $trigger `
  -Settings $settings -Description "Library reminders, holds and GDPR clean-up"
```
Test it now with `Start-ScheduledTask -TaskName "Drumshanbo Library daily job"`, then check `instance\daily-job.log`.
To remove it: `Unregister-ScheduledTask -TaskName "Drumshanbo Library daily job"`.

Each reminder stage is recorded per loan, so it is never sent twice, even if the job runs several
times a day. If the job misses a day it catches up the next day, but it never sends a stale stage
(for example "due soon" after the due date has passed).

---

## 6. Testing on a real phone (optional, Cloudflare Tunnel)

Phones need HTTPS for the service worker and push. A free Cloudflare quick tunnel provides it:
```powershell
winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:5000
```
It prints a `https://….trycloudflare.com` address. Put that in `.env` as `BASE_URL` (so links in
emails point to it), restart `flask run`, and open the address on your phone. The address changes
every time you start the tunnel.

---

## 7. Commands

| Command | What it does |
|---|---|
| `flask send-reminders` | Daily job (see 5) |
| `flask create-admin` | Create a librarian account interactively |
| `flask generate-vapid` | Print new VAPID keys for `.env` |
| `flask seed` | Wipe and load test data (TEST_MODE only) |
| `flask db upgrade` | Apply database migrations |
| `flask db migrate -m "…"` | Create a migration after changing `app/models.py` |
| `scripts\make_icons.ps1` | Rebuild the PWA icons from `app/static/img/logo.svg` (uses Edge headless) |

## 8. Where things are

```
app/
  __init__.py        app factory, blueprints, error pages
  config.py          settings from .env; WELCOME_LINE (Irish text, TO BE VERIFIED) and LIBRARY_NAME
  models.py          User, Book, Loan, ReminderLog, BookRequest, Setting, PushSubscription
  dates.py           today(): the one place the app asks the date (respects "pretend today")
  lending.py         all lending rules and status changes (borrow, return, confirm, request, hold, lost, close account)
  reminders.py       the daily job
  notify.py          email (Flask-Mail → Mailpit) and web push (pywebpush)
  email_templates.py default wording of every email (editable in Settings → Email wording)
  settings.py        editable lending rules and reminder days
  csv_import.py, isbn.py, seed.py, cli.py, forms.py
  blueprints/        main (public), auth, member, admin
  templates/, static/  (css, js incl. sw.js service worker, img/logo.svg, img/icons/)
migrations/          Flask-Migrate (Alembic) scripts
sample_data/books_sample.csv
scripts/             daily_job.ps1, make_icons.ps1
tests/               pytest: lending rules, reminders, requests/holds, date override, web flows
tools/mailpit.exe    local mail catcher (not committed to git)
```

To change the logo, replace `app/static/img/logo.svg` and run `scripts\make_icons.ps1`.
To change the Irish welcome line, edit `WELCOME_LINE` in `app/config.py`.

---

## 9. Milestone report

All four milestones were built in one pass, as agreed.

### Milestone 1: Foundations
**Built:** project structure, models and migrations; login with "remember me" (90 days);
password reset by email (1-hour token with no personal data in it, and it stops working once used);
application → approve/reject (with an optional reason); book add/edit/delete (delete is only allowed
when there is no history); ISBN lookup (Open Library, with a not-found message) plus a camera barcode
scan (html5-qrcode); CSV import with column mapping, a 10-row preview and a report of skipped rows;
public catalogue (Available/Out only; lost and withdrawn books are hidden); PWA manifest, service
worker (offline page) and icons; seed data; TEST MODE banner and quick logins.
**Test:** acceptance tests 1, 7 and 8 above.

### Milestone 2: Lending
**Built:** borrow (confirm screen with the title in large type, then a success screen with the due date);
return with an optional damage note → awaiting check; librarian Confirm on shelf / Not received;
all lending-rule checks (suspended, limit, overdue, hold, re-borrow), each with a plain-English message;
My books (green/amber/red), My history, My details (including password change); admin status override
(on shelf / borrowed by a member / lost / withdrawn); "I've lost this book" (librarian decides:
Found or Confirm lost); close account (blocked while a book is out; personal data deleted; loans
moved to a "Former member" placeholder).
**Test:** acceptance tests 2, 5, 6 and 9.

### Milestone 3: Reminders and requests
**Built:** `flask send-reminders`; all 5 reminder stages, each sent once per loan, with the final
notice copied to the librarian and the loan then listed as Long overdue; returned_pending loans get no
reminders; request + anonymous nudge (one active request per book, and you can't request your own
book); hold on confirm (the clock starts at confirm), only the requester can borrow, expiry with
email; editable email templates; Pretend today; Run reminders now; GDPR clean-up.
**Test:** acceptance tests 3 and 4.

### Milestone 4: Notifications and admin extras
**Built:** web push (VAPID CLI, subscribe button, test push, several devices per admin, removing
dead subscriptions, notification click opens the admin page); librarian email + push for applications
and returns, and email for lost books and final notices; dashboard counts; CSV exports (members,
books, loans); Settings (lending rules, reminder days, librarian email, admin list, create admin);
Task Scheduler instructions.
**Test:** "Push notifications" above; **Settings**; dashboard **Export** buttons.

### Automated tests
`python -m pytest`: 57 tests covering lending rules, every reminder stage day by day (sent once only,
librarian copy, no stale catch-up), request/hold/expiry, the date override (and that it's ignored when
TEST_MODE is off), GDPR clean-up, CSV import of the sample file, mocked ISBN lookup, and the
apply → approve → login, borrow-in-4-taps and return → confirm flows.

### Known gaps and decisions
- **Push was tested with a mocked sender and a browser subscription flow**, not on a real iPhone.
  Desktop Chrome/Edge on localhost should work. iPhone needs the Home Screen install and HTTPS (tunnel).
- **Lost-reported loans don't count** towards the 3-book limit or the overdue block. The spec leaves
  the outcome to the librarian, so a member isn't blocked while it's being sorted. This is easy to change in `lending.counted_loans`.
- **Renewals** default to 0 (none), as in the spec. If set above 0 in Settings, a "Keep it longer" button
  appears (not allowed when overdue or when someone has requested the book).
- **Re-borrowing:** a returned book goes to "awaiting check" first, so the same member can borrow it
  again only after the librarian confirms it on the shelf (and only if nobody has asked for it).
- **Not received** keeps the reminder stages already sent, so the member doesn't get duplicates.
  Later stages still go out on schedule.
- **Admin "Borrowed by…" override** skips the borrowing rules on purpose (the librarian is recording
  what has already happened).
- The member picker on the status override page is a plain dropdown. That's fine for hundreds of members.
- Open Library data quality varies: some ISBNs return odd records, so the admin always reviews before saving.
- Uploaded CSVs are kept in `instance/uploads` only until the import finishes.
- The Irish welcome line and the privacy notice are placeholders (marked in the UI and code).

---

## Moving to production

1. **Server:** a small Linux VPS (e.g. Ubuntu LTS). Copy the project, create the venv, `pip install -r requirements.txt gunicorn`.
2. **App server:** `gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app`, run as a systemd service.
3. **nginx** in front as a reverse proxy, serving `/static/` directly. **HTTPS** with Let's Encrypt (`certbot --nginx`). HTTPS is required for push and the service worker.
4. **Email:** a real SMTP relay (e.g. Brevo or Mailjet). Set `MAIL_SERVER`, `MAIL_PORT=587`, `MAIL_USE_TLS=true`, username and password, and a `MAIL_DEFAULT_SENDER` on your own domain. Set up **SPF and DKIM** DNS records for that domain so reminders don't land in spam.
5. **Daily job:** cron instead of Task Scheduler: `0 8 * * * cd /srv/library && .venv/bin/flask send-reminders >> instance/daily-job.log 2>&1`
6. **Backups:** back up `instance/library.db` nightly (e.g. `sqlite3 library.db ".backup backup-$(date +%F).db"`) and copy it off the server.
7. **`.env`:** `TEST_MODE=false`, a new long `SECRET_KEY`, `BASE_URL=https://your-domain`, new VAPID keys, the real librarian email. Never run `flask seed`.
8. **Content:** real privacy notice (`templates/main/privacy.html`), Irish welcome line checked by an Irish speaker (`app/config.py`), real logo (`static/img/logo.svg` + `scripts/make_icons.ps1`), real book import via CSV, then `flask create-admin` for the librarian.
