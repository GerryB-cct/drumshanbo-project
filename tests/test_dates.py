from datetime import date

from app import settings
from app.dates import real_today, today
from app.extensions import db

from .conftest import START, set_today


def test_today_uses_pretend_date(app):
    assert today() == START
    set_today(date(2027, 1, 15))
    assert today() == date(2027, 1, 15)


def test_clearing_pretend_date_returns_real_date(app):
    settings.delete("pretend_today")
    db.session.commit()
    assert today() == real_today()


def test_pretend_date_ignored_when_test_mode_off(app):
    app.config["TEST_MODE"] = False
    assert today() == real_today()


def test_bad_pretend_value_falls_back_to_real_date(app):
    settings.set("pretend_today", "not-a-date")
    db.session.commit()
    assert today() == real_today()


def test_pretend_today_route_disabled_without_test_mode(app, client):
    from app.models import User

    admin = User(name="Admin", email="a@example.com", role="admin", status="active", address="", phone="")
    admin.set_password("password")
    db.session.add(admin)
    db.session.commit()
    client.post("/account/login", data={"email": "a@example.com", "password": "password"})
    app.config["TEST_MODE"] = False
    assert client.post("/admin/test/pretend-today", data={"date": "2030-01-01"}).status_code == 404
    assert client.post("/admin/test/run-reminders").status_code == 404
    assert client.post("/account/test-login/member").status_code == 404
    assert b"TEST MODE" not in client.get("/").data
