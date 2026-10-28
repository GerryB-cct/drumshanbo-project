# Session report: 28 October 2026

**Project:** Drumshanbo Traditional Irish Music Library, proof of concept
**Folder:** `C:\Users\VelzyG\Documents\lowcode-project\drumshanbo-project`
**Spec:** `SPEC.md` (copied from `Downloads\SPEC (1).md`)

---

## Summary

The whole web application in the spec was built in one session: all four milestones, plus automated
tests and documentation. It runs on this PC at http://localhost:5000, with Mailpit catching every
email at http://localhost:8025. 57 automated tests pass, and acceptance tests 1–8 behaved as the spec
says when run against the live app. The work is committed to git on the `feature/drumshanbo-project`
branch as commit `749ae72`. It has not been pushed to GitHub yet.

## Decisions made at the start

| Question | Decision |
|---|---|
| Stop after each milestone (as the spec says) or build it all? | Build all four in one go, then give one combined report |
| Where should the project live? | `Documents\lowcode-project\drumshanbo-project` (an existing empty git repo on branch `feature/drumshanbo-project`) |
| Install Mailpit? | Yes: downloaded v1.32.0 into `tools\` |
| Include the optional camera barcode scan? | Yes (html5-qrcode) |

## What was built

**Milestone 1: Foundations**
- Flask app with separate public, account, member and librarian sections; SQLite database with migrations.
- Login with "keep me logged in" (90 days) and a forgotten-password email link (valid 1 hour).
- Membership application (18+ and privacy-consent tickboxes) → librarian approves or rejects.
- Book add/edit/delete, ISBN lookup from Open Library, camera barcode scan, CSV import with column matching and a preview.
- Public catalogue showing only "Available" or "Out", never who has a book.
- Installable app (PWA): manifest, service worker, offline page, placeholder Celtic-knot logo and icons.
- Test data: 500 invented books, 15 members covering every loan situation, 2 librarians.
- Test mode banner and "Log in as member / librarian" shortcuts.

**Milestone 2: Lending**
- Borrow in 4 taps; return with an optional damage note; librarian "Confirm on shelf" / "Not received".
- All borrowing rules (suspended, 3-book limit, overdue block, held books), each with a plain-English message.
- My books (green / amber / red), My history, My details, password change, close account.
- "I've lost this book", and the librarian's manual status override.

**Milestone 3: Reminders and requests**
- Daily job (`flask send-reminders`): due soon, due today, 1st and 2nd overdue, and final notice. Each is sent once only, and the final notice is copied to the librarian.
- Request a book that's out: the borrower gets an anonymous nudge, the book is held for 7 days once it's back, and the hold expires automatically.
- Email wording editable in Settings; "Pretend today is…" date control; "Run reminders now" button.
- GDPR clean-up: loan history over 2 years and rejected applications over 30 days are deleted.

**Milestone 4: Notifications and admin extras**
- Web push to librarians' devices (several devices each), with a test push button.
- Librarian email and push for new applications and every return; email for lost books and final notices.
- Dashboard counts, CSV exports (members, books, loans), Settings page, creating extra librarians.
- Daily job script and Windows Task Scheduler instructions.

## Testing done

- **Automated:** 57 pytest tests, all passing. They cover the lending rules, every reminder stage day by day, requests and holds, the date override, GDPR clean-up, CSV import and the main web flows.
- **Against the live app and Mailpit:**
  - apply → approve → log in
  - the anonymous nudge
  - return → Not received
  - the suspended, limit and overdue blocks
  - reminders sent once, with the librarian's copy
  - a second run sending nothing
- **Live ISBN lookup:** 9780140449136 → *Crime and Punishment*; 9798765432104 → "Not found".
- **Push:** a broken device subscription is removed without breaking the page.
- **Phone layout:** checked at 360px wide with screenshots.

## Not done yet / for the owner

- Try push notifications on a real device. iPhones need the app added to the Home Screen first.
- Register the daily 08:00 job in Windows Task Scheduler (the PowerShell is in README §5).
- Test on a real phone via Cloudflare Tunnel (README §6), and have someone non-technical borrow and return a book (acceptance test 9).
- Decide where to push the git branch: the `lowcode-project` GitHub repo, or a new repo of its own.
- Replace the placeholders: the Irish welcome line (needs checking by an Irish speaker), the privacy notice and the logo.

## Decisions taken where the spec was silent

- A book reported lost doesn't count toward the 3-book limit or the overdue block while the librarian sorts it out.
- If the daily job misses days, it sends only the stage a loan has reached, never a stale one.
- The librarian's "Borrowed by…" override skips the borrowing rules, because it records something that has already happened.
- Re-borrowing the same book is possible once the librarian has confirmed it back on the shelf, and only if nobody has asked for it.

## How to run it

Use two PowerShell windows in the project folder:
1. `.\tools\mailpit.exe`
2. `.\.venv\Scripts\Activate.ps1` then `flask run --debug`

Open http://localhost:5000 and use the test-mode login buttons. Every password is `password`.
Full details are in `README.md`.
