"""End-to-end checks through the web pages (acceptance tests 1, 2, 5, 6, 7, 8)."""
import io
import os
import re

from app import isbn as isbn_module
from app.extensions import db
from app.models import Book, Loan, User

from .conftest import login, make_book, make_user

ROOT = os.path.dirname(os.path.dirname(__file__))


def test_public_pages(client, app):
    make_book("The Ballinamore Box Player's Notebook")
    for url in ("/", "/catalogue", "/privacy", "/account/login", "/account/apply", "/manifest.json", "/sw.js"):
        assert client.get(url).status_code == 200, url
    page = client.get("/catalogue?q=Ballinamore").get_data(as_text=True)
    assert "Ballinamore" in page and "Available" in page
    assert "TEST MODE" in page


def test_public_catalogue_hides_lost_and_never_shows_borrower(client, app):
    out = make_book("Out Book")
    make_book("Gone Book").status = "withdrawn"
    db.session.commit()
    from app import lending

    lending.borrow(make_user("Secret Borrower"), out)
    page = client.get("/catalogue").get_data(as_text=True)
    assert "Gone Book" not in page
    assert "Out Book" in page and "Out" in page
    assert "Secret Borrower" not in page


def test_apply_notify_approve_login(client, app, outbox, pushes):
    make_user("Librarian", email="lib@example.com", role="admin")
    resp = client.post("/account/apply", data={
        "name": "Caoimhe Byrne", "address": "5 Church St", "email": "Caoimhe@Example.com",
        "phone": "086 123 4567", "password": "longpassword", "confirm": "longpassword",
        "adult": "y", "consent": "y",
    })
    assert resp.status_code == 302
    user = User.query.filter_by(email="caoimhe@example.com").one()
    assert user.status == "pending" and user.consent_at is not None
    assert any(m.recipients == ["caoimhe@example.com"] for m in outbox)
    assert any(m.recipients == ["librarian@example.com"] and "Caoimhe" in m.subject for m in outbox)
    assert pushes and pushes[0][0] == "New membership application"

    # Pending can't log in yet
    login(client, "caoimhe@example.com", "longpassword")
    assert client.get("/borrow").status_code == 302

    login(client, "lib@example.com")
    client.post(f"/admin/applications/{user.id}/approve")
    assert user.status == "active"
    assert "approved" in outbox[-1].subject
    client.post("/account/logout")

    resp = login(client, "caoimhe@example.com", "longpassword")
    assert resp.status_code == 302
    assert client.get("/borrow").status_code == 200


def test_apply_requires_age_and_consent(client, app):
    page = client.post("/account/apply", data={
        "name": "X", "address": "Y", "email": "x@example.com", "phone": "1",
        "password": "longpassword", "confirm": "longpassword",
    }).get_data(as_text=True)
    assert "You must be 18 or over" in page
    assert "privacy notice" in page
    assert User.query.count() == 0


def test_borrow_in_four_taps(client, app):
    make_user(email="m@example.com")
    book = make_book("The Dromod Flute Tutor")
    login(client, "m@example.com")
    # 1: tap "Borrow a book" on home
    home = client.get("/").get_data(as_text=True)
    assert 'href="/borrow"' in home
    # (type in search box) -> results list
    results = client.get("/borrow?q=Dromod").get_data(as_text=True)
    # 2: tap the book
    assert f'href="/borrow/{book.id}"' in results
    confirm = client.get(f"/borrow/{book.id}").get_data(as_text=True)
    assert "The Dromod Flute Tutor" in confirm and ">Borrow<" in confirm
    # 3: tap "Borrow" -> success screen with due date
    done = client.post(f"/borrow/{book.id}", follow_redirects=True).get_data(as_text=True)
    assert "Please bring it back by" in done
    assert re.search(r"\d{4}", done)
    assert book.status == "on_loan"


def test_blocked_borrow_shows_plain_message(client, app):
    make_user(email="s@example.com", status="suspended")
    book = make_book()
    login(client, "s@example.com")
    page = client.get(f"/borrow/{book.id}").get_data(as_text=True)
    assert "membership is paused" in page
    page = client.post(f"/borrow/{book.id}", follow_redirects=True).get_data(as_text=True)
    assert "membership is paused" in page
    assert Loan.query.count() == 0


def test_return_flow_and_librarian_confirm(client, app, outbox, pushes):
    member = make_user(email="m@example.com")
    make_user("Lib", email="lib@example.com", role="admin")
    book = make_book()
    login(client, "m@example.com")
    client.post(f"/borrow/{book.id}")
    loan = Loan.query.one()
    assert f"/return/{loan.id}" in client.get("/return").get_data(as_text=True)
    page = client.get(f"/return/{loan.id}").get_data(as_text=True)
    assert "Any damage? (optional note)" in page
    client.post(f"/return/{loan.id}", data={"damage_note": "Spine cracked"})
    assert loan.status == "returned_pending" and book.status == "awaiting_check"
    assert pushes and pushes[-1][0] == "Book returned"
    client.post("/account/logout")

    login(client, "lib@example.com")
    awaiting = client.get("/admin/loans?view=awaiting").get_data(as_text=True)
    assert "Spine cracked" in awaiting and "Confirm on shelf" in awaiting and "Not received" in awaiting
    client.post(f"/admin/loans/{loan.id}/confirm")
    assert loan.status == "returned" and book.status == "available"
    assert member.loans.count() == 1


def test_csv_import_sample_file(client, app):
    make_user("Lib", email="lib@example.com", role="admin")
    login(client, "lib@example.com")
    with open(os.path.join(ROOT, "sample_data", "books_sample.csv"), "rb") as fh:
        data = fh.read()
    resp = client.post("/admin/books/import", data={"file": (io.BytesIO(data), "books_sample.csv")},
                       content_type="multipart/form-data")
    assert resp.status_code == 302
    page = client.get("/admin/books/import/map").get_data(as_text=True)
    # Headers were guessed: "Book Title" -> title, "Compiled By" -> author, "Category" -> type
    assert re.search(r'<option value="0" selected>Book Title', page)
    assert re.search(r'<option value="1" selected>Compiled By', page)
    assert re.search(r'<option value="2" selected>Category', page)
    assert "Preview (first 10 rows)" in page
    resp = client.post("/admin/books/import/map", data={
        "map_title": "0", "map_author": "1", "map_book_type": "2", "map_isbn": "3", "map_notes": "4",
        "map_cover_url": "", "default_type": "tune book", "action": "import",
    })
    page = resp.get_data(as_text=True)
    assert Book.query.count() == 21  # 25 rows, 4 deliberately bad
    assert "no title" in page
    assert "not recognised" in page
    assert "not 10 or 13 digits" in page
    assert "already in the catalogue" in page
    assert Book.query.filter_by(title="Mohill Fair Day Songs").one().book_type == "songbook"
    assert Book.query.filter_by(title="Polkas and Slides for the Tin Whistle").one().book_type == "tune book"


def test_isbn_lookup_found_and_not_found(client, app, monkeypatch):
    make_user("Lib", email="lib@example.com", role="admin")
    login(client, "lib@example.com")

    def fake_lookup(code):
        if code == "9780140449136":
            return {"isbn": code, "title": "The Odyssey", "author": "Homer", "cover_url": "https://x/y.jpg"}
        return None

    monkeypatch.setattr(isbn_module, "lookup", fake_lookup)
    found = client.get("/admin/isbn-lookup?isbn=9780140449136").get_json()
    assert found["ok"] and found["title"] == "The Odyssey"
    missing = client.get("/admin/isbn-lookup?isbn=9780000000000")
    assert missing.status_code == 404
    assert missing.get_json()["message"] == "Not found — enter details manually."


def test_admin_area_requires_admin(client, app):
    make_user(email="m@example.com")
    assert client.get("/admin/").status_code == 302  # not logged in -> login page
    login(client, "m@example.com")
    assert client.get("/admin/").status_code == 404


def test_member_search_does_not_put_names_in_url(client, app):
    make_user("Lib", email="lib@example.com", role="admin")
    make_user("Gráinne McKiernan")
    login(client, "lib@example.com")
    page = client.post("/admin/members", data={"q": "Gráinne"}).get_data(as_text=True)
    assert "Gráinne McKiernan" in page
    assert 'method="post"' in page


def test_exports(client, app):
    make_user("Lib", email="lib@example.com", role="admin")
    make_book()
    login(client, "lib@example.com")
    for kind in ("members", "books", "loans"):
        resp = client.get(f"/admin/export/{kind}.csv")
        assert resp.status_code == 200 and resp.mimetype == "text/csv"


def test_password_reset(client, app, outbox):
    make_user(email="m@example.com")
    client.post("/account/forgot", data={"email": "m@example.com"})
    link = re.search(r"http://localhost:5000(/account/reset/\S+)", outbox[-1].body).group(1)
    client.post(link, data={"password": "brandnewpass", "confirm": "brandnewpass"})
    assert login(client, "m@example.com", "brandnewpass").status_code == 302
    # Link can't be reused after the password changed
    assert client.get(link).status_code == 302
    assert "m@example.com" not in link
