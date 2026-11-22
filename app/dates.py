"""The one place the app asks what day it is.

All date logic must call today(). In TEST_MODE an admin can set
"Pretend today is..." and every rule, reminder and hold follows it.
"""
from datetime import date, timedelta

from flask import current_app

from . import settings


def real_today():
    return date.today()


def pretend_date():
    if not current_app.config.get("TEST_MODE"):
        return None
    value = settings.get("pretend_today")
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def today():
    return pretend_date() or real_today()


def add_days(d, days):
    return d + timedelta(days=days)


def nice_date(d):
    """'Tuesday 4 November 2026'"""
    if d is None:
        return ""
    return f"{d:%A} {d.day} {d:%B %Y}"


def short_date(d):
    """'4 Nov 2026'"""
    if d is None:
        return ""
    return f"{d.day} {d:%b %Y}"
