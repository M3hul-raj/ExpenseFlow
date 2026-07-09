"""
utils.py — shared helper functions and constants used across blueprints.

Keeping these here avoids duplicating logic across blueprint files and
prevents circular imports (blueprints import from utils, not from each other).
"""
import calendar as _calendar
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import session
from models import db, User, Expense, Budget

# ── Savings tips ─────────────────────────────────────────────────────────────
TIPS = [
    "Cook at home instead of eating out.",
    "Track your subscriptions.",
    "Plan weekly budgets.",
    "Use public transport to save fuel.",
    "Avoid unnecessary online purchases.",
]


def is_logged_in():
    """Return True if a user session is currently active."""
    return 'user_id' in session


def get_current_year_month():
    """Return the current month in YYYY-MM format."""
    return datetime.now().strftime("%Y-%m")


def get_user_budget(user_id, year_month=None):
    """
    Return the budget amount for a given user and month.
    Priority: explicit Budget row > recurring_budget on User > default 2000.
    """
    if not year_month:
        year_month = get_current_year_month()

    budget = Budget.query.filter_by(user_id=user_id, year_month=year_month).first()
    if budget:
        return budget.amount

    user = db.session.get(User, user_id)
    if user and user.recurring_budget is not None:
        return user.recurring_budget

    return 2000.0  # Default budget


def get_monthly_spending(user_id, year_month):
    """Return total amount spent by a user in the given YYYY-MM month."""
    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date.startswith(year_month)
    ).all()
    return sum(e.amount for e in expenses)


def get_budget_history(user_id, months=6):
    """
    Build a budget vs spending summary for the last N months.
    Returns a list of dicts with keys: month, year_month, budget, spending,
    status ('On Track' / 'Near Limit' / 'Over Budget'), remaining.
    """
    history = []
    current_date = datetime.now()

    for i in range(months):
        date = current_date - relativedelta(months=i)
        year_month = date.strftime("%Y-%m")

        budget_amount = get_user_budget(user_id, year_month)
        spending = get_monthly_spending(user_id, year_month)

        status = "On Track"
        if spending > budget_amount:
            status = "Over Budget"
        elif spending > budget_amount * 0.9:
            status = "Near Limit"

        history.append({
            'month': f"{_calendar.month_name[date.month]} {date.year}",
            'year_month': year_month,
            'budget': budget_amount,
            'spending': spending,
            'status': status,
            'remaining': budget_amount - spending
        })

    return history


def get_user_expenses_sorted(user_id):
    """Return all expenses for a user sorted newest-first by date."""
    expenses = Expense.query.filter_by(user_id=user_id).all()
    expenses.sort(key=lambda x: x.date, reverse=True)
    return expenses
