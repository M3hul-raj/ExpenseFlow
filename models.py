from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    """Stores registered user accounts."""
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False, index=True)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    recurring_budget = db.Column(db.Float, nullable=True)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)

    expenses = db.relationship('Expense', backref='user', lazy=True, cascade="all, delete-orphan")
    budgets  = db.relationship('Budget',  backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        """Hash and store the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify a plain-text password against the stored hash."""
        return check_password_hash(self.password_hash, password)


class Expense(db.Model):
    """Stores individual expense records for a user."""
    id             = db.Column(db.Integer, primary_key=True)
    # Indexed — most queries filter by user_id and/or date
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    date           = db.Column(db.String(10), nullable=False, index=True)  # YYYY-MM-DD
    category       = db.Column(db.String(50), nullable=False)
    amount         = db.Column(db.Float, nullable=False)
    description    = db.Column(db.String(255))
    payment_method = db.Column(db.String(50), default='Cash')
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    # Composite index for the most common query pattern: filter by user then month prefix
    __table_args__ = (
        db.Index('idx_expense_user_date', 'user_id', 'date'),
    )


class Budget(db.Model):
    """Stores monthly budget targets per user."""
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    year_month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    amount     = db.Column(db.Float, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'year_month', name='unique_user_month_budget'),
    )
