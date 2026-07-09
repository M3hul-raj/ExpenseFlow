"""
blueprints/auth.py — authentication and user-profile routes.

Routes: /, /register, /login, /logout, /dashboard, /edit_profile
Blueprint name: 'auth'
Endpoint prefix: auth.<function_name>
"""
import re
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import (
    Blueprint, render_template, request, redirect,
    session, flash, url_for, make_response,
)
from models import db, User
from extensions import limiter
from utils import (
    is_logged_in, get_current_year_month, get_user_budget,
    get_budget_history, get_user_expenses_sorted,
)

logger = logging.getLogger('expenseflow')

auth_bp = Blueprint('auth', __name__)


# ── Landing page ──────────────────────────────────────────────────────────────

@auth_bp.route('/')
def index():
    """Render the public landing page."""
    return render_template('index.html')


# ── Registration ──────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    GET:  Show registration form.
    POST: Validate input, create a new User record, redirect to login.
    Rejects: duplicate usernames/emails, weak passwords, malformed input.
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # ── Server-side validation ────────────────────────────────────────
        if not username or len(username) < 3:
            flash('Username must be at least 3 characters long.', 'error')
            return redirect(url_for('auth.register'))
        if len(username) > 30:
            flash('Username must be 30 characters or fewer.', 'error')
            return redirect(url_for('auth.register'))
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            flash('Username may only contain letters, numbers, and underscores.', 'error')
            return redirect(url_for('auth.register'))
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('auth.register'))
        if not password:
            flash('Password is required.', 'error')
            return redirect(url_for('auth.register'))
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('auth.register'))

        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing_user:
            if existing_user.username == username:
                flash('Username already exists. Please choose a different one.', 'error')
            else:
                flash('Email already exists. Please choose a different one.', 'error')
            return redirect(url_for('auth.register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        logger.info('New user registered: %s (%s)', username, email)

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


# ── Login ─────────────────────────────────────────────────────────────────────

def _login_rate_limit_exceeded(limit):
    """
    Called by Flask-Limiter when the /login POST rate limit is breached.
    Must return a real Response object (not a plain string) so Flask-Limiter
    uses this page instead of its default 429 error response.
    """
    flash(
        'Too many login attempts. Please wait 15 minutes before trying again.',
        'error'
    )
    return make_response(render_template('login.html'), 429)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(
    '5 per 15 minutes',
    methods=['POST'],           # only count POST attempts toward the limit
    error_message='Too many login attempts.',
    on_breach=_login_rate_limit_exceeded,
)
def login():
    """
    GET:  Show login form; redirect to dashboard if already logged in.
    POST: Authenticate credentials, set session, redirect to dashboard.
    Logs failed attempts for auditing.
    """
    if is_logged_in():
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # ── Server-side validation ────────────────────────────────────────
        if not username_or_email:
            flash('Please enter your username or email.', 'error')
            return redirect(url_for('auth.login'))
        if not password:
            flash('Please enter your password.', 'error')
            return redirect(url_for('auth.login'))

        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['email'] = user.email
            session['avatar'] = user.avatar or 'avatar_1'
            session['display_name'] = user.display_name
            logger.info('User logged in: %s', user.username)
            flash('Login successful!', 'success')
            return redirect(url_for('auth.dashboard'))

        # Failed login — log and flash appropriate message
        if not user:
            logger.warning('Login attempt for unknown user: %s', username_or_email)
            flash('User does not exist. Please sign up first!', 'error')
            return redirect(url_for('auth.register'))
        else:
            logger.warning('Wrong password for user: %s', username_or_email)
            flash('Invalid password. Please try again!', 'error')
            return redirect(url_for('auth.login'))

    return render_template('login.html')


# ── Logout ────────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
def logout():
    """Clear the user session and redirect to the landing page."""
    logger.info('User logged out: %s', session.get('username', 'unknown'))
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.index'))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@auth_bp.route('/dashboard')
def dashboard():
    """
    Main authenticated dashboard.
    Computes: monthly spending totals, category/monthly breakdowns,
    budget progress, 6-month budget history, and chart data.
    Determines budget_alert_level ('none' / 'warning' / 'danger')
    for the dismissible banner in the template.
    """
    if not is_logged_in():
        flash('Please log in to access your dashboard.', 'error')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))

    expenses_obj = get_user_expenses_sorted(user_id)

    expenses = []
    total_spent = 0.0
    category_totals = {}
    monthly_totals = {}

    current_year_month = get_current_year_month()
    current_month_spent = 0.0

    for e in expenses_obj:
        expenses.append([e.date, e.category, str(e.amount), e.description, e.payment_method])

        total_spent += e.amount
        category_totals[e.category] = category_totals.get(e.category, 0) + e.amount

        month_key = e.date[:7]
        monthly_totals[month_key] = monthly_totals.get(month_key, 0) + e.amount

        if month_key == current_year_month:
            current_month_spent += e.amount

    days_passed = max(1, datetime.now().day)
    avg_daily_spend = current_month_spent / days_passed
    top_category = max(category_totals, key=category_totals.get) if category_totals else 'None'

    budget = get_user_budget(user_id, current_year_month)
    recurring_budget = user.recurring_budget

    budget_progress = (current_month_spent / budget) * 100 if budget > 0 else 0

    categories = list(category_totals.keys())
    category_amounts = list(category_totals.values())

    # Always produce exactly 6 months of trend data (oldest → newest),
    # filling ₹0 for months that have no recorded expenses.
    months = []
    monthly_amounts = []
    for i in range(5, -1, -1):  # 5 months ago ... current month
        d = datetime.now() - relativedelta(months=i)
        ym = d.strftime('%Y-%m')
        months.append(ym)
        monthly_amounts.append(monthly_totals.get(ym, 0))

    budget_history = get_budget_history(user_id, 6)
    budget_chart_labels = [item['month'] for item in budget_history]
    budget_chart_budgets = [item['budget'] for item in budget_history]
    budget_chart_spending = [item['spending'] for item in budget_history]

    # budget_alert_level is used by the template banner (no flash — handled client-side)
    if budget_progress >= 100:
        budget_alert_level = 'danger'
    elif budget_progress >= 90:
        budget_alert_level = 'warning'
    else:
        budget_alert_level = 'none'

    return render_template('dashboard.html',
                         budget_alert_level=budget_alert_level,
                         expenses=expenses,
                         username=user.username,
                         display_name=user.display_name,
                         user_avatar=user.avatar or 'avatar_1',
                         email=user.email,
                         registration_date=user.registration_date.strftime("%Y-%m-%d %H:%M:%S"),
                         total_spent=total_spent,
                         current_month_spent=current_month_spent,
                         avg_daily_spend=avg_daily_spend,
                         top_category=top_category,
                         budget=budget,
                         recurring_budget=recurring_budget,
                         budget_progress=budget_progress,
                         budget_history=budget_history,
                         categories=categories,
                         category_amounts=category_amounts,
                         months=months,
                         monthly_amounts=monthly_amounts,
                         budget_chart_labels=budget_chart_labels,
                         budget_chart_budgets=budget_chart_budgets,
                         budget_chart_spending=budget_chart_spending,
                         current_date=datetime.now())


# ── Edit Profile ──────────────────────────────────────────────────────────────

@auth_bp.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    """
    GET:  Show the profile edit form with current username/email.
    POST: Validate current password, apply username/email/password changes.
    Prevents duplicate usernames/emails.
    """
    if not is_logged_in():
        flash('Please log in to edit your profile.', 'error')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        new_avatar = request.form.get('avatar', user.avatar or 'avatar_1')
        new_display_name = request.form.get('display_name', '').strip() or None

        if new_username != user.username:
            existing_user = User.query.filter_by(username=new_username).first()
            if existing_user:
                flash('Username already exists. Please choose a different one.', 'error')
                return redirect(url_for('auth.edit_profile'))

        if new_email != user.email:
            existing_email = User.query.filter_by(email=new_email).first()
            if existing_email:
                flash('Email already in use. Please choose a different one.', 'error')
                return redirect(url_for('auth.edit_profile'))

        if new_password:
            if not current_password or not user.check_password(current_password):
                flash('Current password is required and must be correct to set a new password.', 'error')
                return redirect(url_for('auth.edit_profile'))
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('auth.edit_profile'))
            if len(new_password) < 6:
                flash('New password must be at least 6 characters long.', 'error')
                return redirect(url_for('auth.edit_profile'))
            user.set_password(new_password)

        user.username = new_username
        user.email = new_email
        user.avatar = new_avatar
        user.display_name = new_display_name
        db.session.commit()

        session['username'] = new_username
        session['email'] = new_email
        session['avatar'] = new_avatar
        session['display_name'] = new_display_name

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.dashboard'))

    reg_date = user.registration_date.strftime('%B %d, %Y') if user.registration_date else 'Unknown'
    return render_template('edit_profile.html',
                           username=user.username,
                           email=user.email,
                           current_avatar=user.avatar or 'avatar_1',
                           display_name=user.display_name,
                           registration_date=reg_date)
