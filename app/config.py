import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")

load_dotenv(os.path.join(BASE_DIR, ".env"))

LIBRARY_NAME = "The Drumshanbo Traditional Irish Music Library"

# TO BE VERIFIED by an Irish speaker before going live.
WELCOME_LINE = "Fáilte go Leabharlann Cheoil Dhroim Seanbhó"


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-not-secret"
    BASE_URL = os.environ.get("BASE_URL") or "http://localhost:5000"
    TEST_MODE = env_bool("TEST_MODE", False)

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + os.path.join(INSTANCE_DIR, "library.db").replace("\\", "/")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REMEMBER_COOKIE_DURATION = timedelta(days=90)
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PASSWORD_RESET_MAX_AGE = 3600  # seconds

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # CSV uploads

    MAIL_SERVER = os.environ.get("MAIL_SERVER") or "localhost"
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 1025)
    MAIL_USE_TLS = env_bool("MAIL_USE_TLS", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME") or None
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD") or None
    MAIL_DEFAULT_SENDER = (
        LIBRARY_NAME,
        os.environ.get("MAIL_DEFAULT_SENDER") or "library@drumshanbo-music-library.example",
    )

    LIBRARIAN_EMAIL = os.environ.get("LIBRARIAN_EMAIL") or "librarian@example.com"

    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY") or ""
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY") or ""
    VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL") or "mailto:librarian@example.com"


class TestConfig(Config):
    TESTING = True
    TEST_MODE = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    SERVER_NAME = None
    VAPID_PUBLIC_KEY = "test-public"
    VAPID_PRIVATE_KEY = "test-private"
