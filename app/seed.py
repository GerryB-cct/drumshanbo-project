"""Invented test data (flask seed). All names, titles and addresses are made up."""
import random
from datetime import datetime

from . import settings
from .dates import add_days, today
from .extensions import db
from .models import (
    AVAILABLE,
    AWAITING_CHECK,
    LOST,
    ON_HOLD,
    ON_LOAN,
    Book,
    BookRequest,
    Loan,
    PushSubscription,
    ReminderLog,
    Setting,
    User,
)

PASSWORD = "password"

PLACES = [
    "Leitrim", "Sligo", "Roscommon", "Clare", "Kerry", "Donegal", "Mayo", "Galway", "Fermanagh",
    "Cavan", "Longford", "Drumshanbo", "Ballinamore", "Carrick-on-Shannon", "Arigna", "Keshcarrigan",
    "Dromod", "Mohill", "Tulla", "Kilfenora", "Dowra", "Glenfarne", "Manorhamilton", "Kinlough",
    "Drumkeerin", "Leitrim Village", "Ballyfarnon", "Boyle", "Gort", "Miltown Malbay",
]
REGIONS = [
    "Iron Mountains", "Shannon Banks", "Lough Allen Shore", "Arigna Valley", "Sliabh an Iarainn",
    "Upper Shannon", "Bog Road", "North Connacht", "Breifne Hills", "West Clare Coast",
]
INSTRUMENTS = [
    "Fiddle", "Tin Whistle", "Flute", "Uilleann Pipes", "Button Accordion", "Concertina", "Banjo",
    "Harp", "Mandolin", "Bouzouki", "Low Whistle", "Piano Accompaniment",
]
PLAYERS = ["Fiddler", "Piper", "Flute Player", "Whistler", "Box Player", "Harper", "Concertina Player", "Singer"]
TUNE_TYPES = [
    "Reels", "Jigs", "Hornpipes", "Slides", "Polkas", "Slip Jigs", "Mazurkas", "Barndances",
    "Set Dances", "Slow Airs", "Marches", "Waltzes", "Flings",
]
SURNAMES = [
    "Duignan", "McNamara", "Rynn", "Reynolds", "Moran", "Gaffney", "McDermott", "Gallagher",
    "O'Rourke", "Cryan", "Flynn", "Mulvey", "McKiernan", "Beirne", "Cullen", "Guckian", "McGovern",
    "Shanley", "Lynch", "Dolan", "Keaney", "Mahon", "Feely", "Tansey", "Conlon",
]
FIRST_NAMES = [
    "Mary", "Seán", "Aoife", "Pádraig", "Niamh", "Ciarán", "Bríd", "Tomás", "Síle", "Declan",
    "Orla", "Liam", "Gráinne", "Eoin", "Maeve", "Michael", "Kathleen", "Joe", "Peggy", "Francie",
]
SONG_BOOK_NAMES = [
    "Shannon", "Lough Allen", "Iron Mountain", "Kitchen Session", "Fireside", "Crossroads",
    "Céilí Hall", "Harvest Fair", "Emigrant's", "Sean-nós", "Townland",
]
DECADES = ["1890s", "1920s", "1930s", "1950s", "1960s", "1970s"]


def _title_generators(r):
    tune = [
        lambda: f"The {r.choice(PLACES)} {r.choice(PLAYERS)}'s Companion, Vol. {r.randint(1, 4)}",
        lambda: f"{r.choice([50, 60, 75, 100, 101, 120, 150, 200])} {r.choice(TUNE_TYPES)} for the {r.choice(INSTRUMENTS)}",
        lambda: f"Tunes from the {r.choice(REGIONS)}: {r.choice(TUNE_TYPES)} and {r.choice(TUNE_TYPES)}",
        lambda: f"The {r.choice(SURNAMES)} Collection of {r.choice(TUNE_TYPES)}",
        lambda: f"Session Tunes from {r.choice(PLACES)}, Book {r.randint(1, 5)}",
        lambda: f"{r.choice(TUNE_TYPES)} from the {r.choice(SURNAMES)} Manuscripts",
        lambda: f"{r.choice(INSTRUMENTS)} Tutor for Beginners, Part {r.randint(1, 3)}",
        lambda: f"The {r.choice(PLACES)} Céilí Band Book",
        lambda: f"Music of the {r.choice(REGIONS)}, Vol. {r.randint(1, 3)}",
        lambda: f"A {r.choice(PLACES)} {r.choice(PLAYERS)}'s Notebook",
    ]
    song = [
        lambda: f"Songs of {r.choice(PLACES)}",
        lambda: f"{r.choice(PLACES)} Songs and Ballads",
        lambda: f"The {r.choice(SONG_BOOK_NAMES)} Songbook, Book {r.randint(1, 4)}",
        lambda: f"Ballads of the {r.choice(REGIONS)}",
        lambda: f"Come-All-Ye's from {r.choice(PLACES)}",
        lambda: f"Songs My {r.choice(['Grandmother', 'Grandfather', 'Mother', 'Father', 'Aunt'])} Sang in {r.choice(PLACES)}",
    ]
    ref = [
        lambda: f"A History of the {r.choice(INSTRUMENTS)} in {r.choice(PLACES)}",
        lambda: f"Regional Styles of {r.choice(PLACES)} {r.choice(INSTRUMENTS)} Playing",
        lambda: f"Collectors and Collections: {r.choice(PLACES)} Music in the {r.choice(DECADES)}",
        lambda: f"The {r.choice(SURNAMES)} Family: Musicians of {r.choice(PLACES)}",
        lambda: f"Understanding Ornamentation on the {r.choice(INSTRUMENTS)}",
        lambda: f"Dancing Masters of {r.choice(PLACES)}",
        lambda: f"House Dances and Crossroads Dances of {r.choice(PLACES)}",
    ]
    return tune, song, ref


def make_titles(n=500, seed=1916):
    r = random.Random(seed)
    tune, song, ref = _title_generators(r)
    books = {}
    while len(books) < n:
        roll = r.random()
        if roll < 0.62:
            kind, gens = "tune book", tune
        elif roll < 0.87:
            kind, gens = "songbook", song
        else:
            kind, gens = "reference", ref
        title = r.choice(gens)()
        if title in books:
            continue
        if r.random() < 0.12:
            author = f"{r.choice(PLACES)} Comhaltas Branch"
        else:
            author = f"{r.choice(FIRST_NAMES)} {r.choice(SURNAMES)}"
        notes = None
        if r.random() < 0.1:
            notes = r.choice([
                "Spiral bound. Includes chord symbols.",
                "Some pages loose — handle with care.",
                "Donated by a local family.",
                "Comes with a CD in the back pocket.",
                "Large print edition.",
            ])
        books[title] = (kind, author, notes)
    return [(t, *v) for t, v in books.items()]


MEMBERS = [
    # (name, email)
    ("Mary Test", "member@example.com"),
    ("Seán Kelly", "sean.kelly@example.com"),
    ("Aoife Gallagher", "aoife.gallagher@example.com"),
    ("Pádraig Moran", "padraig.moran@example.com"),
    ("Niamh Reynolds", "niamh.reynolds@example.com"),
    ("Ciarán McDermott", "ciaran.mcdermott@example.com"),
    ("Bríd Flynn", "brid.flynn@example.com"),
    ("Tomás Duignan", "tomas.duignan@example.com"),
    ("Síle O'Rourke", "sile.orourke@example.com"),
    ("Declan Mulvey", "declan.mulvey@example.com"),
    ("Orla Gaffney", "orla.gaffney@example.com"),
    ("Liam Cryan", "liam.cryan@example.com"),
    ("Gráinne McKiernan", "grainne.mckiernan@example.com"),
    ("Eoin Rynn", "eoin.rynn@example.com"),
    ("Maeve Beirne", "maeve.beirne@example.com"),
]

STREETS = ["Main Street", "Carrick Road", "Church Street", "Convent Avenue", "Lough Allen Road", "Arigna Road"]


def _wipe():
    for model in (ReminderLog, PushSubscription, BookRequest, Loan, Book, User, Setting):
        db.session.query(model).delete()
    db.session.commit()


def _person(r, name, email, role="member", status="active", applied=None):
    t = today()
    user = User(
        name=name,
        email=email,
        address=f"{r.randint(1, 60)} {r.choice(STREETS)}, Drumshanbo, Co. Leitrim",
        phone=f"08{r.choice('3579')} {r.randint(100, 999)} {r.randint(1000, 9999)}",
        role=role,
        status=status,
        adult_confirmed=True,
        consent_at=datetime.now(),
        applied_on=applied or add_days(t, -r.randint(100, 900)),
    )
    if status in ("active", "suspended"):
        user.approved_on = add_days(user.applied_on, 2)
    user.set_password(PASSWORD)
    db.session.add(user)
    return user


def seed():
    r = random.Random(42)
    _wipe()
    t = today()

    # Books
    books = []
    for title, kind, author, notes in make_titles():
        book = Book(title=title, author=author, book_type=kind, notes=notes, status=AVAILABLE)
        db.session.add(book)
        books.append(book)
    db.session.flush()
    pool = books[:]
    r.shuffle(pool)

    def next_book():
        return pool.pop()

    # People
    admins = [
        _person(r, "Úna Librarian", "librarian@example.com", role="admin"),
        _person(r, "Martin Admin", "admin2@example.com", role="admin"),
    ]
    members = [_person(r, name, email) for name, email in MEMBERS]
    m = {email.split("@")[0]: u for u, (_n, email) in zip(members, MEMBERS)}
    m["liam.cryan"].status = "suspended"
    _person(r, "Caoimhe Byrne", "caoimhe.byrne@example.com", status="pending", applied=add_days(t, -2))
    rejected = _person(r, "Rejected Applicant", "rejected.applicant@example.com", status="rejected",
                       applied=add_days(t, -40))
    rejected.rejected_on = add_days(t, -35)
    rejected.reject_reason = "Test record: should be deleted by the daily job (over 30 days old)."
    db.session.flush()

    def loan(user, due_in, status="on_loan", stages=(), book=None, **extra):
        book = book or next_book()
        due = add_days(t, due_in)
        ln = Loan(book=book, user=user, borrowed_on=add_days(due, -28), due_on=due, status=status, **extra)
        db.session.add(ln)
        for stage in stages:
            db.session.add(ReminderLog(loan=ln, stage=stage, sent_on=t))
        book.status = {"on_loan": ON_LOAN, "returned_pending": AWAITING_CHECK, "lost_reported": LOST}.get(status, AVAILABLE)
        return ln

    # Current loans covering every state
    loan(m["member"], 14)                                              # green
    loan(m["member"], 2)                                               # amber
    loan(m["sean.kelly"], 3)                                           # due in 3 days -> "due soon"
    loan(m["aoife.gallagher"], 0, stages=["due_soon"])                 # due today
    loan(m["padraig.moran"], -7, stages=["due_soon", "due_today"])     # 7 days overdue
    loan(m["niamh.reynolds"], -14, stages=["due_soon", "due_today", "overdue_1"])
    loan(m["ciaran.mcdermott"], -28, stages=["due_soon", "due_today", "overdue_1", "overdue_2"])
    loan(m["brid.flynn"], -40, stages=["due_soon", "due_today", "overdue_1", "overdue_2", "final_notice"])
    for due_in in (5, 12, 20):                                         # at the 3-book limit
        loan(m["grainne.mckiernan"], due_in)

    # Requested: Tomás has it, Síle has asked for it
    requested = loan(m["tomas.duignan"], 10)
    db.session.add(BookRequest(book=requested.book, user=m["sile.orourke"], status="waiting",
                               created_on=add_days(t, -1)))

    # Awaiting check: Declan tapped "return" yesterday
    loan(m["declan.mulvey"], 6, status="returned_pending", returned_on=add_days(t, -1),
         damage_note="Cover is a bit torn at the corner, sorry!")

    # Lost report
    loan(m["orla.gaffney"], 9, status="lost_reported", lost_reported_on=add_days(t, -2))

    # On hold for Mary (demo member), and one for Eoin that expires the day after tomorrow
    for user, started in ((m["member"], -2), (m["eoin.rynn"], -6)):
        held = next_book()
        loan(m["maeve.beirne"], started - 3, status="returned", book=held,
                    returned_on=add_days(t, started - 1), closed_on=add_days(t, started))
        held.status = ON_HOLD
        db.session.add(BookRequest(
            book=held, user=user, status="on_hold", created_on=add_days(t, started - 10),
            hold_started_on=add_days(t, started), hold_until=add_days(t, started + 7),
        ))

    # Past history (some older than 2 years, to show the GDPR clean-up)
    for user in members:
        for _ in range(r.randint(1, 5)):
            closed = add_days(t, -r.randint(40, 700))
            book = r.choice(books)
            db.session.add(Loan(book=book, user=user, borrowed_on=add_days(closed, -25),
                                due_on=add_days(closed, -25 + 28), status="returned",
                                returned_on=add_days(closed, -1), closed_on=closed))
    for user in members[:3]:
        closed = add_days(t, -800)
        db.session.add(Loan(book=r.choice(books), user=user, borrowed_on=add_days(closed, -20),
                            due_on=add_days(closed, 8), status="returned",
                            returned_on=closed, closed_on=closed))

    settings.set("librarian_email", "librarian@example.com")
    db.session.commit()

    return [
        f"Seeded {len(books)} books, {len(members)} members, {len(admins)} admins, "
        "1 pending and 1 rejected application.",
        f"All test accounts use the password: {PASSWORD}",
        "  Member:    member@example.com",
        "  Librarian: librarian@example.com  (also admin2@example.com)",
        "  Suspended: liam.cryan@example.com",
        "  At limit:  grainne.mckiernan@example.com",
        "  Overdue:   padraig.moran@example.com",
    ]
