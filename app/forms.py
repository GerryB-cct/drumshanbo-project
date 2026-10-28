from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    BooleanField,
    EmailField,
    PasswordField,
    SelectField,
    StringField,
    TelField,
    TextAreaField,
)
from wtforms.validators import URL, DataRequired, Email, EqualTo, Length, Optional

from .models import BOOK_TYPES

REQ = "Please fill this in."


class LoginForm(FlaskForm):
    email = EmailField("Email address", validators=[DataRequired(REQ), Email("Please enter a valid email address.")])
    password = PasswordField("Password", validators=[DataRequired(REQ)])
    remember = BooleanField("Keep me logged in on this device")


class _DetailsMixin:
    name = StringField("Full name", validators=[DataRequired(REQ), Length(max=120)])
    address = TextAreaField("Address", validators=[DataRequired(REQ), Length(max=500)])
    email = EmailField("Email address", validators=[DataRequired(REQ), Email("Please enter a valid email address.")])
    phone = TelField("Phone number", validators=[DataRequired(REQ), Length(max=40)])


class ApplyForm(_DetailsMixin, FlaskForm):
    password = PasswordField(
        "Choose a password",
        validators=[DataRequired(REQ), Length(min=8, message="Please use at least 8 characters.")],
    )
    confirm = PasswordField(
        "Type the password again",
        validators=[DataRequired(REQ), EqualTo("password", message="The two passwords don't match.")],
    )
    adult = BooleanField("I confirm I am 18 or over", validators=[DataRequired("You must be 18 or over to join.")])
    consent = BooleanField(
        "I agree to the library using my details as described in the privacy notice",
        validators=[DataRequired("Please tick this box to agree to the privacy notice.")],
    )


class DetailsForm(_DetailsMixin, FlaskForm):
    pass


class PasswordChangeForm(FlaskForm):
    current = PasswordField("Current password", validators=[DataRequired(REQ)])
    password = PasswordField(
        "New password",
        validators=[DataRequired(REQ), Length(min=8, message="Please use at least 8 characters.")],
    )
    confirm = PasswordField(
        "Type the new password again",
        validators=[DataRequired(REQ), EqualTo("password", message="The two passwords don't match.")],
    )


class ForgotForm(FlaskForm):
    email = EmailField("Email address", validators=[DataRequired(REQ), Email("Please enter a valid email address.")])


class ResetForm(FlaskForm):
    password = PasswordField(
        "New password",
        validators=[DataRequired(REQ), Length(min=8, message="Please use at least 8 characters.")],
    )
    confirm = PasswordField(
        "Type the new password again",
        validators=[DataRequired(REQ), EqualTo("password", message="The two passwords don't match.")],
    )


class AdminCreateForm(_DetailsMixin, FlaskForm):
    password = PasswordField(
        "Password",
        validators=[DataRequired(REQ), Length(min=8, message="Please use at least 8 characters.")],
    )


class BookForm(FlaskForm):
    isbn = StringField("ISBN (optional)", validators=[Optional(), Length(max=20)])
    title = StringField("Title", validators=[DataRequired(REQ), Length(max=300)])
    author = StringField("Author / compiler", validators=[Optional(), Length(max=200)])
    book_type = SelectField("Type", choices=[(t, t.capitalize()) for t in BOOK_TYPES])
    notes = TextAreaField("Notes (optional)", validators=[Optional(), Length(max=2000)])
    cover_url = StringField(
        "Cover image URL (optional)",
        validators=[Optional(), URL(message="Please enter a full web address."), Length(max=500)],
    )


class CsvUploadForm(FlaskForm):
    file = FileField(
        "CSV file",
        validators=[FileRequired("Please choose a file."), FileAllowed(["csv", "txt"], "Please choose a .csv file.")],
    )
