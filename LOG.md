# Log

Newest first.

## 2026-10-28: PoC built (all 4 milestones)

- Built the full PoC from `SPEC.md` in one pass (owner chose this over stopping after each milestone).
- Decisions agreed at the start: project lives in `Documents\lowcode-project\drumshanbo-project`;
  Mailpit downloaded into `tools\` (v1.32.0); html5-qrcode barcode scan included.
- Python 3.15.0 venv. All dependencies installed from wheels without problems.
- 57 pytest tests pass. Ran live checks against `flask run` + Mailpit: apply → approve → login,
  request nudge, return → Not received, all three borrowing blocks, reminders (each stage once,
  final notice copied to the librarian, second run sends nothing).
- Real Open Library lookup checked: 9780140449136 → "Crime and punishment". 9798765432104 → not found.
- Checked phone layout at 360px with headless Edge screenshots.
- Known gaps: see README §9 ("Known gaps and decisions"). Push hasn't been tried on a real phone yet.

**Next:** owner to test on a phone (Chrome DevTools mobile view, then Cloudflare Tunnel), enable push
on a device, and register the Task Scheduler job.
