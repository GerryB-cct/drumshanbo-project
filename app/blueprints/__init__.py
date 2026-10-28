from functools import wraps

from flask import abort, current_app
from flask_login import current_user, login_required


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(404)
        return view(*args, **kwargs)

    return wrapped


def test_mode_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_app.config["TEST_MODE"]:
            abort(404)
        return view(*args, **kwargs)

    return wrapped
