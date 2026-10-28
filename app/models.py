from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

# Book status values
AVAILABLE = "available"
ON_LOAN = "on_loan"
AWAITING_CHECK = "awaiting_check"
ON_HOLD = "on_hold"
LOST = "lost"
WITHDRAWN = "withdrawn"
BOOK_STATUSES = [AVAILABLE, ON_LOAN, AWAITING_CHECK, ON_HOLD, LOST, WITHDRAWN]
HIDDEN_STATUSES = [LOST, WITHDRAWN]

BOOK_TYPES = ["tune book", "songbook", "reference"]

# Loan status values
LOAN_ON_LOAN = "on_loan"
LOAN_RETURNED_PENDING = "returned_pending"
LOAN_RETURNED = "returned"
LOAN_LOST_REPORTED = "lost_reported"
LOAN_LOST = "lost"
OPEN_LOAN_STATUSES = [LOAN_ON_LOAN, LOAN_RETURNED_PENDING, LOAN_LOST_REPORTED]

# Request status values
REQ_WAITING = "waiting"
REQ_ON_HOLD = "on_hold"
REQ_FULFILLED = "fulfilled"
REQ_EXPIRED = "expired"
REQ_CANCELLED = "cancelled"
ACTIVE_REQUEST_STATUSES = [REQ_WAITING, REQ_ON_HOLD]


def utcnow():
    return datetime.now()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.Text, nullable=False, default="")
    email = db.Column(db.String(255), unique=True, index=True)
    phone = db.Column(db.String(40), nullable=False, default="")
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(20), nullable=False, default="member")  # member | admin | placeholder
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending | active | suspended | rejected
    adult_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    consent_at = db.Column(db.DateTime)
    applied_on = db.Column(db.Date)
    approved_on = db.Column(db.Date)
    rejected_on = db.Column(db.Date)
    reject_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)

    loans = db.relationship("Loan", back_populates="user", lazy="dynamic")
    requests = db.relationship("BookRequest", back_populates="user", lazy="dynamic")
    push_subscriptions = db.relationship(
        "PushSubscription", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_suspended(self):
        return self.status == "suspended"

    @property
    def first_name(self):
        return (self.name or "").split(" ")[0]

    def current_loans(self):
        return (
            self.loans.filter(Loan.status == LOAN_ON_LOAN).order_by(Loan.due_on).all()
        )

    def open_loans(self):
        return self.loans.filter(Loan.status.in_(OPEN_LOAN_STATUSES)).order_by(Loan.due_on).all()


@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    if user and user.status in ("active", "suspended"):
        return user
    return None


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False, index=True)
    author = db.Column(db.String(200), nullable=False, default="")
    book_type = db.Column(db.String(20), nullable=False, default="tune book")
    isbn = db.Column(db.String(20), index=True)
    notes = db.Column(db.Text)
    cover_url = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default=AVAILABLE, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    loans = db.relationship("Loan", back_populates="book", lazy="dynamic")
    requests = db.relationship("BookRequest", back_populates="book", lazy="dynamic")

    @property
    def is_public(self):
        return self.status not in HIDDEN_STATUSES

    @property
    def public_status(self):
        return "Available" if self.status == AVAILABLE else "Out"

    def open_loan(self):
        return self.loans.filter(Loan.status.in_(OPEN_LOAN_STATUSES)).order_by(Loan.id.desc()).first()

    def active_request(self):
        return (
            self.requests.filter(BookRequest.status.in_(ACTIVE_REQUEST_STATUSES))
            .order_by(BookRequest.id)
            .first()
        )


class Loan(db.Model):
    __tablename__ = "loans"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    borrowed_on = db.Column(db.Date, nullable=False)
    due_on = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=LOAN_ON_LOAN, index=True)
    returned_on = db.Column(db.Date)  # when the member tapped "return"
    closed_on = db.Column(db.Date)  # when the librarian confirmed / closed it
    lost_reported_on = db.Column(db.Date)
    damage_note = db.Column(db.Text)
    renewals = db.Column(db.Integer, nullable=False, default=0)

    book = db.relationship("Book", back_populates="loans")
    user = db.relationship("User", back_populates="loans")
    reminders = db.relationship("ReminderLog", back_populates="loan", cascade="all, delete-orphan")

    def days_overdue(self, today):
        return (today - self.due_on).days

    def is_overdue(self, today):
        return self.status == LOAN_ON_LOAN and self.due_on < today

    def due_colour(self, today, amber_days=3):
        days_left = (self.due_on - today).days
        if days_left < 0:
            return "red"
        if days_left <= amber_days:
            return "amber"
        return "green"

    def stages_sent(self):
        return {r.stage for r in self.reminders}


class ReminderLog(db.Model):
    __tablename__ = "reminder_logs"
    __table_args__ = (db.UniqueConstraint("loan_id", "stage", name="uq_reminder_loan_stage"),)

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loans.id"), nullable=False, index=True)
    stage = db.Column(db.String(20), nullable=False)
    sent_on = db.Column(db.Date, nullable=False)

    loan = db.relationship("Loan", back_populates="reminders")


class BookRequest(db.Model):
    __tablename__ = "book_requests"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=REQ_WAITING, index=True)
    created_on = db.Column(db.Date, nullable=False)
    hold_started_on = db.Column(db.Date)
    hold_until = db.Column(db.Date)
    closed_on = db.Column(db.Date)

    book = db.relationship("Book", back_populates="requests")
    user = db.relationship("User", back_populates="requests")


class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")


class PushSubscription(db.Model):
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)
    device_label = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User", back_populates="push_subscriptions")

    def as_subscription_info(self):
        return {"endpoint": self.endpoint, "keys": {"p256dh": self.p256dh, "auth": self.auth}}
