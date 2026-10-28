import logging
import os

from flask import Flask, render_template

from . import config as app_config
from .config import Config
from .extensions import csrf, db, login_manager, mail, migrate


def create_app(config_class=Config):
    app = Flask(__name__, instance_path=app_config.INSTANCE_DIR, instance_relative_config=False)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)
    logging.basicConfig(level=logging.INFO)

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    from .blueprints.admin import bp as admin_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.main import bp as main_bp
    from .blueprints.member import bp as member_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(member_bp)
    app.register_blueprint(admin_bp)

    from . import cli

    cli.register(app)

    from .dates import nice_date, pretend_date, short_date, today

    app.jinja_env.filters["nice_date"] = nice_date
    app.jinja_env.filters["short_date"] = short_date

    @app.context_processor
    def inject_globals():
        test_mode = app.config["TEST_MODE"]
        return {
            "LIBRARY_NAME": app_config.LIBRARY_NAME,
            "WELCOME_LINE": app_config.WELCOME_LINE,
            "TEST_MODE": test_mode,
            "PRETEND_DATE": pretend_date() if test_mode else None,
            "TODAY": today(),
        }

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("main/error.html", title="Page not found",
                               message="Sorry, we couldn't find that page."), 404

    @app.errorhandler(400)
    def bad_request(_e):
        return render_template("main/error.html", title="Something went wrong",
                               message="Sorry, that didn't work. Please go back and try again."), 400

    @app.errorhandler(500)
    def server_error(_e):
        db.session.rollback()
        return render_template("main/error.html", title="Something went wrong",
                               message="Sorry, something went wrong on our side. Please try again."), 500

    return app
