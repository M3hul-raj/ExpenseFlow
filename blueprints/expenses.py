"""
blueprints/expenses.py — expense CRUD routes.

Routes: /add, /view, /edit/<id>, /delete/<id>
Blueprint name: 'expenses'
Endpoint prefix: expenses.<function_name>
"""
import re as _re
import logging
import random
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect,
    session, flash, url_for,
)
from models import db, Expense
from utils import (
    is_logged_in, get_current_year_month, get_user_budget,
    get_user_expenses_sorted, TIPS,
)

logger = logging.getLogger('expenseflow')

expenses_bp = Blueprint('expenses', __name__)

# ── Shared validation sets ────────────────────────────────────────────────────
VALID_CATEGORIES = {
    'Food', 'Transport', 'Shopping', 'Entertainment', 'Health',
    'Utilities', 'Education', 'Travel', 'Personal Care', 'Home', 'Insurance', 'Other'
}
VALID_METHODS = {
    'Cash', 'UPI', 'Credit Card', 'Debit Card', 'Net Banking', 'Digital Wallet', 'Other'
}


# ── Add expense ───────────────────────────────────────────────────────────────

@expenses_bp.route('/add', methods=['GET', 'POST'])
def add_expense():
    """
    GET:  Show the add-expense form with current budget context.
    POST: Validate all fields server-side, persist a new Expense record.
    Validation: date format, category whitelist, positive amount cap,
    payment method whitelist, description length.
    """
    if not is_logged_in():
        flash('Please log in to add expenses.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        date            = request.form.get('date', '').strip()
        category        = request.form.get('category', '').strip()
        amount_raw      = request.form.get('amount', '').strip()
        description     = request.form.get('description', '').strip()
        payment_method  = request.form.get('payment_method', '').strip()

        # ── Server-side validation ────────────────────────────────────────
        if not date or not _re.match(r'\d{4}-\d{2}-\d{2}', date):
            flash('Please select a valid date.', 'error')
            return redirect(url_for('expenses.add_expense'))
        # Reject future dates
        try:
            expense_date = datetime.strptime(date, '%Y-%m-%d').date()
            if expense_date > datetime.now().date():
                flash('Expense date cannot be in the future.', 'error')
                return redirect(url_for('expenses.add_expense'))
        except ValueError:
            flash('Please select a valid date.', 'error')
            return redirect(url_for('expenses.add_expense'))
        if category not in VALID_CATEGORIES:
            flash('Please select a valid category.', 'error')
            return redirect(url_for('expenses.add_expense'))
        if not amount_raw:
            flash('Amount is required.', 'error')
            return redirect(url_for('expenses.add_expense'))
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
            if amount > 10_000_000:
                flash('Amount seems too large. Please check your entry.', 'warning')
                return redirect(url_for('expenses.add_expense'))
        except ValueError:
            flash('Please enter a valid positive amount.', 'error')
            return redirect(url_for('expenses.add_expense'))
        if payment_method not in VALID_METHODS:
            flash('Please select a valid payment method.', 'error')
            return redirect(url_for('expenses.add_expense'))
        # Sanitise description
        description = description[:255]

        # ── Persist to database ───────────────────────────────────────────
        user_id = session['user_id']
        new_expense = Expense(
            user_id=user_id,
            date=date,
            category=category,
            amount=amount,
            description=description,
            payment_method=payment_method
        )
        db.session.add(new_expense)
        db.session.commit()
        logger.info('Expense added: user=%s amount=%.2f category=%s', user_id, amount, category)

        flash('Expense added successfully!', 'success')
        return redirect(url_for('auth.dashboard'))

    # GET — compute budget context for the info strip
    user_id = session['user_id']

    current_ym = get_current_year_month()
    month_spent = sum(
        e.amount for e in Expense.query.filter(
            Expense.user_id == user_id,
            Expense.date.startswith(current_ym)
        ).all()
    )
    add_budget = get_user_budget(user_id, current_ym)
    add_budget_remaining = add_budget - month_spent
    add_budget_pct = (month_spent / add_budget * 100) if add_budget > 0 else 0

    return render_template('add_expense.html',
        current_date=datetime.now(),
        budget=add_budget,
        budget_spent=month_spent,
        budget_remaining=add_budget_remaining,
        budget_pct=add_budget_pct,
    )


# ── View / list expenses ──────────────────────────────────────────────────────

@expenses_bp.route('/view')
def view_expense():
    """
    Transactions list page.
    Aggregates all user expenses into category, monthly and payment-method
    totals for the filter UI; passes the raw expense list for JS filtering.
    """
    if not is_logged_in():
        flash('Please log in to view expenses.', 'error')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    expenses_obj = get_user_expenses_sorted(user_id)

    expenses = []
    total_spent = 0.0
    category_totals = {}
    monthly_totals = {}
    payment_method_totals = {}

    for e in expenses_obj:
        expenses.append([e.date, e.category, str(e.amount), e.description, e.payment_method, e.id])

        total_spent += e.amount
        category_totals[e.category] = category_totals.get(e.category, 0) + e.amount
        payment_method_totals[e.payment_method] = payment_method_totals.get(e.payment_method, 0) + e.amount

        month_key = e.date[:7]
        monthly_totals[month_key] = monthly_totals.get(month_key, 0) + e.amount

    if expenses_obj:
        first_date = datetime.strptime(min(e.date for e in expenses_obj), '%Y-%m-%d').date()
        days_active = max(1, (datetime.now().date() - first_date).days + 1)
        avg_daily_spend = total_spent / days_active
    else:
        avg_daily_spend = 0
    top_category = max(category_totals, key=category_totals.get) if category_totals else 'None'
    top_payment_method = max(payment_method_totals, key=payment_method_totals.get) if payment_method_totals else 'None'

    sorted_category_totals = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    sorted_monthly_totals = sorted(monthly_totals.items(), key=lambda x: x[0], reverse=True)
    sorted_payment_method_totals = sorted(payment_method_totals.items(), key=lambda x: x[1], reverse=True)

    savings_tip = random.choice(TIPS) if TIPS else "Track your expenses regularly!"

    return render_template('view_expense.html',
                         expenses=expenses,
                         total_spent=total_spent,
                         category_totals=sorted_category_totals,
                         monthly_totals=sorted_monthly_totals,
                         payment_method_totals=sorted_payment_method_totals,
                         avg_daily_spend=avg_daily_spend,
                         top_category=top_category,
                         top_payment_method=top_payment_method,
                         savings_tip=savings_tip,
                         current_date=datetime.now())


# ── Edit expense ──────────────────────────────────────────────────────────────

@expenses_bp.route('/edit/<int:expense_id>', methods=['GET', 'POST'])
def edit_expense(expense_id):
    """
    GET:  Load an existing expense into the edit form.
    POST: Validate and persist the updated fields.
    expense_id is the database primary key (Expense.id), scoped to the
    logged-in user so one user cannot edit another user's expense.
    """
    if not is_logged_in():
        flash('Please log in to edit expenses.', 'error')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    expense_to_edit = Expense.query.filter_by(id=expense_id, user_id=user_id).first_or_404()

    if request.method == 'POST':
        date           = request.form.get('date', '').strip()
        category       = request.form.get('category', '').strip()
        amount_raw     = request.form.get('amount', '').strip()
        description    = request.form.get('description', '').strip()
        payment_method = request.form.get('payment_method', '').strip()

        if not date or not _re.match(r'\d{4}-\d{2}-\d{2}', date):
            flash('Please select a valid date.', 'error')
            return redirect(url_for('expenses.edit_expense', expense_id=expense_id))
        try:
            if datetime.strptime(date, '%Y-%m-%d').date() > datetime.now().date():
                flash('Expense date cannot be in the future.', 'error')
                return redirect(url_for('expenses.edit_expense', expense_id=expense_id))
        except ValueError:
            flash('Please select a valid date.', 'error')
            return redirect(url_for('expenses.edit_expense', expense_id=expense_id))
        if category not in VALID_CATEGORIES:
            flash('Please select a valid category.', 'error')
            return redirect(url_for('expenses.edit_expense', expense_id=expense_id))
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash('Please enter a valid positive amount.', 'error')
            return redirect(url_for('expenses.edit_expense', expense_id=expense_id))
        if payment_method not in VALID_METHODS:
            flash('Please select a valid payment method.', 'error')
            return redirect(url_for('expenses.edit_expense', expense_id=expense_id))
        description = description[:255]

        expense_to_edit.date = date
        expense_to_edit.category = category
        expense_to_edit.amount = amount
        expense_to_edit.description = description
        expense_to_edit.payment_method = payment_method

        db.session.commit()
        logger.info('Expense edited: user=%s id=%s', user_id, expense_to_edit.id)

        flash('Expense updated successfully!', 'success')
        return redirect(url_for('expenses.view_expense'))

    expense_list = [expense_to_edit.date, expense_to_edit.category, str(expense_to_edit.amount), expense_to_edit.description, expense_to_edit.payment_method]
    return render_template('edit_expense.html', expense=expense_list, expense_id=expense_id)


# ── Delete expense ────────────────────────────────────────────────────────────

@expenses_bp.route('/delete/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    """
    Delete the expense identified by its database primary key (Expense.id).
    Accepts POST only — GET requests are rejected with 405 Method Not Allowed.
    The query is scoped to the logged-in user so one user cannot delete
    another user's expense.
    Redirects to the transactions page with a success or error flash.
    """
    if not is_logged_in():
        flash('Please log in to delete expenses.', 'error')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    expense_to_delete = Expense.query.filter_by(id=expense_id, user_id=user_id).first_or_404()

    db.session.delete(expense_to_delete)
    db.session.commit()
    logger.info('Expense deleted: user=%s id=%s', user_id, expense_to_delete.id)
    flash('Expense deleted successfully!', 'success')

    return redirect(url_for('expenses.view_expense'))
