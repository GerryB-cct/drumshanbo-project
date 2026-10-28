import base64

import click
from flask import current_app

from .extensions import db
from .models import User


def register(app):
    @app.cli.command("send-reminders")
    def send_reminders_cmd():
        """Daily job: reminders, hold expiry and GDPR clean-up."""
        from . import reminders

        summary = reminders.run_daily()
        for line in reminders.summary_lines(summary):
            click.echo(line)

    @app.cli.command("create-admin")
    def create_admin_cmd():
        """Create a librarian (admin) account interactively."""
        name = click.prompt("Full name")
        email = click.prompt("Email").strip().lower()
        if User.query.filter_by(email=email).first():
            raise click.ClickException("An account with that email already exists.")
        phone = click.prompt("Phone", default="", show_default=False)
        address = click.prompt("Address", default="", show_default=False)
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        if len(password) < 8:
            raise click.ClickException("Please use at least 8 characters.")
        user = User(name=name, email=email, phone=phone, address=address,
                    role="admin", status="active", adult_confirmed=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin {email} created.")

    @app.cli.command("generate-vapid")
    def generate_vapid_cmd():
        """Generate VAPID keys for web push and print the .env lines."""
        from cryptography.hazmat.primitives import serialization
        from py_vapid import Vapid01

        vapid = Vapid01()
        vapid.generate_keys()
        raw_private = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
        raw_public = vapid.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )

        def b64(data):
            return base64.urlsafe_b64encode(data).decode().rstrip("=")

        click.echo("Paste these lines into your .env file, then restart the app:\n")
        click.echo(f"VAPID_PUBLIC_KEY={b64(raw_public)}")
        click.echo(f"VAPID_PRIVATE_KEY={b64(raw_private)}")
        if current_app.config.get("VAPID_PRIVATE_KEY"):
            click.echo("\nWarning: keys are already set. Replacing them means every device "
                       "must tap 'Enable notifications' again.")

    @app.cli.command("seed")
    @click.option("--yes", is_flag=True, help="Don't ask for confirmation.")
    def seed_cmd(yes):
        """Wipe the database and load test data (TEST_MODE only)."""
        if not current_app.config["TEST_MODE"]:
            raise click.ClickException("Seeding is only allowed when TEST_MODE=true.")
        if not yes:
            click.confirm("This deletes ALL data and loads test data. Continue?", abort=True)
        from .seed import seed

        for line in seed():
            click.echo(line)
