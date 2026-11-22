from datetime import date

import pytest

from app import create_app, notify, settings
from app.config import TestConfig
from app.extensions import db, mail
from app.models import Book, User

START = date(2026, 3, 2)  # a Monday


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        settings.set("pretend_today", START.isoformat())
        settings.set("librarian_email", "librarian@example.com")
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def outbox(app):
    with mail.record_messages() as messages:
        yield messages


@pytest.fixture
def pushes(monkeypatch):
    """Capture push notifications instead of sending them."""
    sent = []
    monkeypatch.setattr(notify, "push_admins", lambda title, body, url="/": sent.append((title, body, url)) or 1)
    return sent


@pytest.fixture
def client(app):
    return app.test_client()


def set_today(d):
    settings.set("pretend_today", d.isoformat())
    db.session.commit()


def make_user(name="Test Member", email=None, status="active", role="member"):
    email = email or f"{name.lower().replace(' ', '.')}@example.com"
    user = User(name=name, email=email, address="1 Main St", phone="087 000 0000",
                status=status, role=role, adult_confirmed=True)
    user.set_password("password")
    db.session.add(user)
    db.session.commit()
    return user


def make_book(title="The Leitrim Fiddler's Companion, Vol. 2"):
    book = Book(title=title, author="A. Compiler", book_type="tune book", status="available")
    db.session.add(book)
    db.session.commit()
    return book


def login(client, email, password="password"):
    return client.post("/account/login", data={"email": email, "password": password}, follow_redirects=False)
