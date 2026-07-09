"""
blueprints/budget.py — budget management routes.

Routes: /set_budget, /adjust_budget, /quick_adjust_budget
Blueprint name: 'budget'
Endpoint prefix: budget.<function_name>
"""
import logging
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect,
    session, flash, url_for,
)
from models import db, User, Budget
from utils import is_logged_in, get_current_year_month, get_user_budget

logger = logging.getLogger('expenseflow')

budget_bp = Blueprint('budget', __name__)


# ── Set budget ────────────────────────────────────────────────────────────────

@budget_bp.route('/set_budget', methods=['GET', 'POST'])
def set_budget():
    """
    GET:  Show the set-budget form with the current month's budget pre-filled.
    POST: Validate the submitted budget amount, upsert the Budget record.
          If 'recurring' checkbox is checked, also update user.recurring_budget.
    """
    if not is_logged_in():
        flash('Please log in to set your budget.', 'error')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    current_year_month = get_current_year_month()
    current_budget = get_user_budget(user_id, current_year_month)

    if request.method == 'POST':
        try:
            month = request.form['month']
            year = request.form['year']
            year_month = f"{year}-{month}"
            new_budget_amount = float(request.form['budget'])

            if new_budget_amount <= 0:
                flash('Budget must be a positive number.', 'error')
                return redirect(url_for('budget.set_budget'))

            budget = Budget.query.filter_by(user_id=user_id, year_month=year_month).first()
            if budget:
                budget.amount = new_budget_amount
            else:
                budget = Budget(user_id=user_id, year_month=year_month, amount=new_budget_amount)
                db.session.add(budget)

            if 'recurring' in request.form:
                user = db.session.get(User, user_id)
                if user:
                    user.recurring_budget = new_budget_amount
                flash(f'Recurring budget set to ₹{new_budget_amount:.2f}! This will be applied to future months.', 'success')
            else:
                flash(f'Budget for {month}/{year} updated successfully!', 'success')

            db.session.commit()
            return redirect(url_for('auth.dashboard'))

        except ValueError:
            flash('Please enter a valid budget amount.', 'error')
            return redirect(url_for('budget.set_budget'))

    return render_template('set_budget.html',
                         current_budget=current_budget,
                         current_month=datetime.now().strftime("%m"),
                         current_year=datetime.now().year)


# ── Adjust budget ─────────────────────────────────────────────────────────────

@budget_bp.route('/adjust_budget', methods=['POST'])
def adjust_budget():
    """
    Increase or decrease the current month's budget by a given amount.
    Reads 'adjustment_type' ('increase'|'decrease') and 'adjustment_amount' from POST.
    """
    if not is_logged_in():
        flash('Please log in to adjust your budget.', 'error')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    current_year_month = get_current_year_month()

    try:
        adjustment_type = request.form.get('adjustment_type')
        adjustment_amount = float(request.form.get('adjustment_amount', 0))

        if adjustment_amount <= 0:
            flash('Adjustment amount must be a positive number.', 'error')
            return redirect(url_for('auth.dashboard'))

        current_budget_amount = get_user_budget(user_id, current_year_month)

        if adjustment_type == 'increase':
            new_budget_amount = current_budget_amount + adjustment_amount
            message = f'Budget increased by ₹{adjustment_amount:.2f}! New budget: ₹{new_budget_amount:.2f}'
        elif adjustment_type == 'decrease':
            new_budget_amount = max(0, current_budget_amount - adjustment_amount)
            message = f'Budget decreased by ₹{adjustment_amount:.2f}! New budget: ₹{new_budget_amount:.2f}'
        else:
            flash('Invalid adjustment type.', 'error')
            return redirect(url_for('auth.dashboard'))

        budget = Budget.query.filter_by(user_id=user_id, year_month=current_year_month).first()
        if budget:
            budget.amount = new_budget_amount
        else:
            budget = Budget(user_id=user_id, year_month=current_year_month, amount=new_budget_amount)
            db.session.add(budget)

        db.session.commit()
        flash(message, 'success')
        return redirect(url_for('auth.dashboard'))

    except ValueError:
        flash('Please enter a valid adjustment amount.', 'error')
        return redirect(url_for('auth.dashboard'))


# ── Quick adjust budget ───────────────────────────────────────────────────────

@budget_bp.route('/quick_adjust_budget', methods=['POST'])
def quick_adjust_budget():
    """
    Quick ± budget adjustment from the dashboard modal.
    Reads 'action' ('add'|'subtract') and 'quick_amount' from POST.
    """
    if not is_logged_in():
        flash('Please log in to adjust your budget.', 'error')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    current_year_month = get_current_year_month()

    try:
        quick_amount = float(request.form.get('quick_amount', 0))
        action = request.form.get('action')

        if quick_amount <= 0:
            flash('Invalid adjustment amount.', 'error')
            return redirect(url_for('auth.dashboard'))

        current_budget_amount = get_user_budget(user_id, current_year_month)

        if action == 'add':
            new_budget_amount = current_budget_amount + quick_amount
        elif action == 'subtract':
            new_budget_amount = max(0, current_budget_amount - quick_amount)
        else:
            flash('Invalid action.', 'error')
            return redirect(url_for('auth.dashboard'))

        budget = Budget.query.filter_by(user_id=user_id, year_month=current_year_month).first()
        if budget:
            budget.amount = new_budget_amount
        else:
            budget = Budget(user_id=user_id, year_month=current_year_month, amount=new_budget_amount)
            db.session.add(budget)

        db.session.commit()
        flash(f'Budget adjusted by ₹{quick_amount:.2f}! New budget: ₹{new_budget_amount:.2f}', 'success')
        return redirect(url_for('auth.dashboard'))

    except ValueError:
        flash('Invalid adjustment amount.', 'error')
        return redirect(url_for('auth.dashboard'))
