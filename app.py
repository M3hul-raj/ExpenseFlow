import logging
from flask import Flask, render_template, request, redirect, session, flash, url_for
from datetime import datetime
import random, os
from dateutil.relativedelta import relativedelta
from models import db, User, Expense, Budget

# ── Logging setup ─────────────────────────────────────────────────────────────
# Logs to a rotating file in the project root; INFO level for general events,
# WARNING/ERROR for security/DB issues.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('expenseflow.log', encoding='utf-8'),
        logging.StreamHandler(),         # also print to console in dev
    ]
)
logger = logging.getLogger('expenseflow')

app = Flask(__name__)
# --- CUSTOM JINJA FILTERS ---
@app.template_filter('currency')
def format_currency(value):
    """Formats a float/int into Indian Rupee format."""
    try:
        value = float(value)
        return f"₹{value:,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"

# SECRET_KEY: read from environment in production; use a strong fallback for dev
app.secret_key = os.environ.get('EXPENSEFLOW_SECRET_KEY', 'dev-only-fallback-change-in-prod-!@#')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

# ── Error handlers ────────────────────────────────────────────────────────────
@app.errorhandler(404)
def page_not_found(e):
    """Render a branded 404 page for any missing route."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    """Render a branded 500 page for any unhandled server error."""
    db.session.rollback()  # safety: clear any broken transaction
    return render_template('500.html'), 500

# Static tips to replace TIPS_FILE
TIPS = [
    "Cook at home instead of eating out.",
    "Track your subscriptions.",
    "Plan weekly budgets.",
    "Use public transport to save fuel.",
    "Avoid unnecessary online purchases."
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
    import calendar
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
            'month': f"{calendar.month_name[date.month]} {date.year}",
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

@app.route('/')
def index():
    """Render the public landing page."""
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
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
        import re
        if not username or len(username) < 3:
            flash('Username must be at least 3 characters long.', 'error')
            return redirect(url_for('register'))
        if len(username) > 30:
            flash('Username must be 30 characters or fewer.', 'error')
            return redirect(url_for('register'))
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            flash('Username may only contain letters, numbers, and underscores.', 'error')
            return redirect(url_for('register'))
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('register'))
        if not password:
            flash('Password is required.', 'error')
            return redirect(url_for('register'))
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('register'))

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            if existing_user.username == username:
                flash('Username already exists. Please choose a different one.', 'error')
            else:
                flash('Email already exists. Please choose a different one.', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        logger.info('New user registered: %s (%s)', username, email)

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    GET:  Show login form; redirect to dashboard if already logged in.
    POST: Authenticate credentials, set session, redirect to dashboard.
    Logs failed attempts for auditing.
    """
    if is_logged_in():
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # ── Server-side validation ────────────────────────────────────────
        if not username_or_email:
            flash('Please enter your username or email.', 'error')
            return redirect(url_for('login'))
        if not password:
            flash('Please enter your password.', 'error')
            return redirect(url_for('login'))

        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['email'] = user.email
            logger.info('User logged in: %s', user.username)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))

        # Failed login — log and flash appropriate message
        if not user:
            logger.warning('Login attempt for unknown user: %s', username_or_email)
            flash('User does not exist. Please sign up first!', 'error')
            return redirect(url_for('register'))
        else:
            logger.warning('Wrong password for user: %s', username_or_email)
            flash('Invalid password. Please try again!', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Clear the user session and redirect to the landing page."""
    logger.info('User logged out: %s', session.get('username', 'unknown'))
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
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
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return redirect(url_for('login'))

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

    unique_dates = set(e.date for e in expenses_obj)
    avg_daily_spend = total_spent / max(1, len(unique_dates))
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

@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    """
    GET:  Show the add-expense form with current budget context.
    POST: Validate all fields server-side, persist a new Expense record.
    Validation: date format, category whitelist, positive amount cap,
    payment method whitelist, description length.
    """
    if not is_logged_in():
        flash('Please log in to add expenses.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        date            = request.form.get('date', '').strip()
        category        = request.form.get('category', '').strip()
        amount_raw      = request.form.get('amount', '').strip()
        description     = request.form.get('description', '').strip()
        payment_method  = request.form.get('payment_method', '').strip()

        # ── Server-side validation ────────────────────────────────────────
        VALID_CATEGORIES = {
            'Food','Transport','Shopping','Entertainment','Health',
            'Utilities','Education','Travel','Personal Care','Home','Insurance','Other'
        }
        VALID_METHODS = {'Cash','UPI','Credit Card','Debit Card','Net Banking','Digital Wallet','Other'}
        import re as _re
        if not date or not _re.match(r'\d{4}-\d{2}-\d{2}', date):
            flash('Please select a valid date.', 'error')
            return redirect(url_for('add_expense'))
        # Reject future dates
        try:
            expense_date = datetime.strptime(date, '%Y-%m-%d').date()
            if expense_date > datetime.now().date():
                flash('Expense date cannot be in the future.', 'error')
                return redirect(url_for('add_expense'))
        except ValueError:
            flash('Please select a valid date.', 'error')
            return redirect(url_for('add_expense'))
        if category not in VALID_CATEGORIES:
            flash('Please select a valid category.', 'error')
            return redirect(url_for('add_expense'))
        if not amount_raw:
            flash('Amount is required.', 'error')
            return redirect(url_for('add_expense'))
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
            if amount > 10_000_000:
                flash('Amount seems too large. Please check your entry.', 'warning')
                return redirect(url_for('add_expense'))
        except ValueError:
            flash('Please enter a valid positive amount.', 'error')
            return redirect(url_for('add_expense'))
        if payment_method not in VALID_METHODS:
            flash('Please select a valid payment method.', 'error')
            return redirect(url_for('add_expense'))
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
        return redirect(url_for('dashboard'))

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
    # threshold for badge/strip colour: 90%

    return render_template('add_expense_updated.html',
        current_date=datetime.now(),
        budget=add_budget,
        budget_spent=month_spent,
        budget_remaining=add_budget_remaining,
        budget_pct=add_budget_pct,
    )

@app.route('/view')
def view_expense():
    """
    Transactions list page.
    Aggregates all user expenses into category, monthly and payment-method
    totals for the filter UI; passes the raw expense list for JS filtering.
    """
    if not is_logged_in():
        flash('Please log in to view expenses.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    expenses_obj = get_user_expenses_sorted(user_id)
    
    expenses = []
    total_spent = 0.0
    category_totals = {}
    monthly_totals = {}
    payment_method_totals = {}

    for e in expenses_obj:
        expenses.append([e.date, e.category, str(e.amount), e.description, e.payment_method])
        
        total_spent += e.amount
        category_totals[e.category] = category_totals.get(e.category, 0) + e.amount
        payment_method_totals[e.payment_method] = payment_method_totals.get(e.payment_method, 0) + e.amount
        
        month_key = e.date[:7]
        monthly_totals[month_key] = monthly_totals.get(month_key, 0) + e.amount

    unique_dates = set(e.date for e in expenses_obj)
    avg_daily_spend = total_spent / max(1, len(unique_dates))
    top_category = max(category_totals, key=category_totals.get) if category_totals else 'None'
    top_payment_method = max(payment_method_totals, key=payment_method_totals.get) if payment_method_totals else 'None'

    sorted_category_totals = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    sorted_monthly_totals = sorted(monthly_totals.items(), key=lambda x: x[0], reverse=True)
    sorted_payment_method_totals = sorted(payment_method_totals.items(), key=lambda x: x[1], reverse=True)

    savings_tip = random.choice(TIPS) if TIPS else "Track your expenses regularly!"

    return render_template('view_expense_updated.html',
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

@app.route('/edit/<int:expense_index>', methods=['GET', 'POST'])
def edit_expense(expense_index):
    """
    GET:  Load an existing expense into the edit form.
    POST: Validate and persist the updated fields.
    expense_index is a positional index into the user's date-sorted expense list.
    """
    if not is_logged_in():
        flash('Please log in to edit expenses.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    expenses_obj = get_user_expenses_sorted(user_id)

    if not (0 <= expense_index < len(expenses_obj)):
        flash('Invalid expense index.', 'error')
        return redirect(url_for('view_expense'))

    expense_to_edit = expenses_obj[expense_index]

    if request.method == 'POST':
        import re as _re
        date           = request.form.get('date', '').strip()
        category       = request.form.get('category', '').strip()
        amount_raw     = request.form.get('amount', '').strip()
        description    = request.form.get('description', '').strip()
        payment_method = request.form.get('payment_method', '').strip()

        VALID_CATEGORIES = {
            'Food','Transport','Shopping','Entertainment','Health',
            'Utilities','Education','Travel','Personal Care','Home','Insurance','Other'
        }
        VALID_METHODS = {'Cash','UPI','Credit Card','Debit Card','Net Banking','Digital Wallet','Other'}

        if not date or not _re.match(r'\d{4}-\d{2}-\d{2}', date):
            flash('Please select a valid date.', 'error')
            return redirect(url_for('edit_expense', expense_index=expense_index))
        try:
            if datetime.strptime(date, '%Y-%m-%d').date() > datetime.now().date():
                flash('Expense date cannot be in the future.', 'error')
                return redirect(url_for('edit_expense', expense_index=expense_index))
        except ValueError:
            flash('Please select a valid date.', 'error')
            return redirect(url_for('edit_expense', expense_index=expense_index))
        if category not in VALID_CATEGORIES:
            flash('Please select a valid category.', 'error')
            return redirect(url_for('edit_expense', expense_index=expense_index))
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash('Please enter a valid positive amount.', 'error')
            return redirect(url_for('edit_expense', expense_index=expense_index))
        if payment_method not in VALID_METHODS:
            flash('Please select a valid payment method.', 'error')
            return redirect(url_for('edit_expense', expense_index=expense_index))
        description = description[:255]

        expense_to_edit.date = date
        expense_to_edit.category = category
        expense_to_edit.amount = amount
        expense_to_edit.description = description
        expense_to_edit.payment_method = payment_method

        db.session.commit()
        logger.info('Expense edited: user=%s id=%s', user_id, expense_to_edit.id)

        flash('Expense updated successfully!', 'success')
        return redirect(url_for('view_expense'))


    expense_list = [expense_to_edit.date, expense_to_edit.category, str(expense_to_edit.amount), expense_to_edit.description, expense_to_edit.payment_method]
    return render_template('edit_expense.html', expense=expense_list, expense_index=expense_index)

@app.route('/delete/<int:expense_index>')
def delete_expense(expense_index):
    """
    Delete the expense at the given positional index in the user's sorted list.
    Redirects to the transactions page with a success or error flash.
    """
    if not is_logged_in():
        flash('Please log in to delete expenses.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    expenses_obj = get_user_expenses_sorted(user_id)

    if 0 <= expense_index < len(expenses_obj):
        expense_to_delete = expenses_obj[expense_index]
        db.session.delete(expense_to_delete)
        db.session.commit()
        logger.info('Expense deleted: user=%s id=%s', user_id, expense_to_delete.id)
        flash('Expense deleted successfully!', 'success')
    else:
        logger.warning('Invalid delete index %s for user %s', expense_index, user_id)
        flash('Expense not found.', 'error')

    return redirect(url_for('view_expense'))

@app.route('/set_budget', methods=['GET', 'POST'])
def set_budget():
    """
    GET:  Show the set-budget form with the current month's budget pre-filled.
    POST: Validate the submitted budget amount, upsert the Budget record.
          If 'recurring' checkbox is checked, also update user.recurring_budget.
    """
    if not is_logged_in():
        flash('Please log in to set your budget.', 'error')
        return redirect(url_for('login'))

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
                return redirect(url_for('set_budget'))

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
            return redirect(url_for('dashboard'))

        except ValueError:
            flash('Please enter a valid budget amount.', 'error')
            return redirect(url_for('set_budget'))

    return render_template('set_budget.html',
                         current_budget=current_budget,
                         current_month=datetime.now().strftime("%m"),
                         current_year=datetime.now().year)

@app.route('/adjust_budget', methods=['POST'])
def adjust_budget():
    """
    Increase or decrease the current month's budget by a given amount.
    Reads 'adjustment_type' ('increase'|'decrease') and 'adjustment_amount' from POST.
    """
    if not is_logged_in():
        flash('Please log in to adjust your budget.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    current_year_month = get_current_year_month()

    try:
        adjustment_type = request.form.get('adjustment_type')
        adjustment_amount = float(request.form.get('adjustment_amount', 0))

        if adjustment_amount <= 0:
            flash('Adjustment amount must be a positive number.', 'error')
            return redirect(url_for('dashboard'))

        current_budget_amount = get_user_budget(user_id, current_year_month)

        if adjustment_type == 'increase':
            new_budget_amount = current_budget_amount + adjustment_amount
            message = f'Budget increased by ₹{adjustment_amount:.2f}! New budget: ₹{new_budget_amount:.2f}'
        elif adjustment_type == 'decrease':
            new_budget_amount = max(0, current_budget_amount - adjustment_amount)
            message = f'Budget decreased by ₹{adjustment_amount:.2f}! New budget: ₹{new_budget_amount:.2f}'
        else:
            flash('Invalid adjustment type.', 'error')
            return redirect(url_for('dashboard'))

        budget = Budget.query.filter_by(user_id=user_id, year_month=current_year_month).first()
        if budget:
            budget.amount = new_budget_amount
        else:
            budget = Budget(user_id=user_id, year_month=current_year_month, amount=new_budget_amount)
            db.session.add(budget)

        db.session.commit()
        flash(message, 'success')
        return redirect(url_for('dashboard'))

    except ValueError:
        flash('Please enter a valid adjustment amount.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/quick_adjust_budget', methods=['POST'])
def quick_adjust_budget():
    """
    Quick ± budget adjustment from the dashboard modal.
    Reads 'action' ('add'|'subtract') and 'quick_amount' from POST.
    """
    if not is_logged_in():
        flash('Please log in to adjust your budget.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    current_year_month = get_current_year_month()

    try:
        quick_amount = float(request.form.get('quick_amount', 0))
        action = request.form.get('action')

        if quick_amount <= 0:
            flash('Invalid adjustment amount.', 'error')
            return redirect(url_for('dashboard'))

        current_budget_amount = get_user_budget(user_id, current_year_month)

        if action == 'add':
            new_budget_amount = current_budget_amount + quick_amount
        elif action == 'subtract':
            new_budget_amount = max(0, current_budget_amount - quick_amount)
        else:
            flash('Invalid action.', 'error')
            return redirect(url_for('dashboard'))

        budget = Budget.query.filter_by(user_id=user_id, year_month=current_year_month).first()
        if budget:
            budget.amount = new_budget_amount
        else:
            budget = Budget(user_id=user_id, year_month=current_year_month, amount=new_budget_amount)
            db.session.add(budget)

        db.session.commit()
        flash(f'Budget adjusted by ₹{quick_amount:.2f}! New budget: ₹{new_budget_amount:.2f}', 'success')
        return redirect(url_for('dashboard'))

    except ValueError:
        flash('Invalid adjustment amount.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    """
    GET:  Show the profile edit form with current username/email.
    POST: Validate current password, apply username/email/password changes.
    Prevents duplicate usernames/emails.
    """
    if not is_logged_in():
        flash('Please log in to edit your profile.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if not user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('edit_profile'))

        if new_username != user.username:
            existing_user = User.query.filter_by(username=new_username).first()
            if existing_user:
                flash('Username already exists. Please choose a different one.', 'error')
                return redirect(url_for('edit_profile'))

        if new_email != user.email:
            existing_email = User.query.filter_by(email=new_email).first()
            if existing_email:
                flash('Email already in use. Please choose a different one.', 'error')
                return redirect(url_for('edit_profile'))

        if new_password:
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('edit_profile'))
            if len(new_password) < 6:
                flash('New password must be at least 6 characters long.', 'error')
                return redirect(url_for('edit_profile'))
            user.set_password(new_password)

        user.username = new_username
        user.email = new_email
        db.session.commit()

        session['username'] = new_username
        session['email'] = new_email

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_profile.html', username=user.username, email=user.email)

@app.route('/analytics')
def analytics():
    """
    Spending analytics page with 9 sections:
    KPI cards, trend banner, category breakdown + table, MoM grouped bar,
    daily bar chart, payment method chart, top 5 expenses, calendar heatmap.
    Accepts ?month=YYYY-MM query param to switch months.
    """
    if not is_logged_in():
        flash('Please log in to access analytics.', 'error')
        return redirect(url_for('login'))

    import calendar as cal_module
    user_id = session['user_id']
    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return redirect(url_for('login'))

    # ── Selected month (from query param or current) ──────────────────────
    selected_month = request.args.get('month', get_current_year_month())
    try:
        sel_dt = datetime.strptime(selected_month, "%Y-%m")
    except ValueError:
        sel_dt = datetime.now()
        selected_month = sel_dt.strftime("%Y-%m")

    prev_dt = sel_dt - relativedelta(months=1)
    prev_month = prev_dt.strftime("%Y-%m")

    # ── Fetch expenses ─────────────────────────────────────────────────────
    month_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date.startswith(selected_month)
    ).order_by(Expense.amount.desc()).all()

    prev_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date.startswith(prev_month)
    ).all()

    all_expenses = Expense.query.filter_by(user_id=user_id).all()

    # ── Available months for selector ─────────────────────────────────────
    all_months_raw = sorted(set(e.date[:7] for e in all_expenses), reverse=True)
    available_months = [
        {'value': m, 'label': datetime.strptime(m, "%Y-%m").strftime("%B %Y")}
        for m in all_months_raw
    ]
    if not any(m['value'] == selected_month for m in available_months):
        available_months.insert(0, {
            'value': selected_month,
            'label': sel_dt.strftime("%B %Y")
        })

    # ── Basic totals ───────────────────────────────────────────────────────
    total_this_month = sum(e.amount for e in month_expenses)
    total_prev_month = sum(e.amount for e in prev_expenses)

    if total_prev_month > 0:
        mom_change_pct = ((total_this_month - total_prev_month) / total_prev_month) * 100
    else:
        mom_change_pct = 0.0
    mom_direction = 'up' if mom_change_pct > 0 else ('down' if mom_change_pct < 0 else 'flat')

    # ── Active days ────────────────────────────────────────────────────────
    active_days = len(set(e.date for e in month_expenses))

    # ── Biggest expense ────────────────────────────────────────────────────
    biggest_expense = month_expenses[0] if month_expenses else None

    # ── Daily totals (for bar chart + calendar) ────────────────────────────
    days_in_month = cal_module.monthrange(sel_dt.year, sel_dt.month)[1]
    daily_totals = {}
    for e in month_expenses:
        day = int(e.date[8:10])
        daily_totals[day] = daily_totals.get(day, 0) + e.amount

    daily_labels = list(range(1, days_in_month + 1))
    daily_amounts = [round(daily_totals.get(d, 0), 2) for d in daily_labels]
    peak_day = max(daily_totals, key=daily_totals.get) if daily_totals else None
    peak_day_amount = daily_totals.get(peak_day, 0) if peak_day else 0

    # ── Category breakdown ─────────────────────────────────────────────────
    cat_totals = {}
    for e in month_expenses:
        cat_totals[e.category] = cat_totals.get(e.category, 0) + e.amount
    cat_totals_sorted = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
    cat_labels = [c[0] for c in cat_totals_sorted]
    cat_amounts = [round(c[1], 2) for c in cat_totals_sorted]
    cat_percentages = [
        round((c[1] / total_this_month * 100), 1) if total_this_month > 0 else 0
        for c in cat_totals_sorted
    ]

    # ── Category MoM change (for trend banner) ─────────────────────────────
    prev_cat_totals = {}
    for e in prev_expenses:
        prev_cat_totals[e.category] = prev_cat_totals.get(e.category, 0) + e.amount

    cat_mom = {}
    for cat, amt in cat_totals.items():
        prev_amt = prev_cat_totals.get(cat, 0)
        cat_mom[cat] = amt - prev_amt
    biggest_increase_cat = max(cat_mom, key=cat_mom.get) if cat_mom else None
    biggest_increase_amt = cat_mom.get(biggest_increase_cat, 0) if biggest_increase_cat else 0

    # ── Payment method breakdown ───────────────────────────────────────────
    pay_totals = {}
    for e in month_expenses:
        method = e.payment_method or 'Other'
        pay_totals[method] = pay_totals.get(method, 0) + e.amount
    pay_totals_sorted = sorted(pay_totals.items(), key=lambda x: x[1], reverse=True)
    pay_labels = [p[0] for p in pay_totals_sorted]
    pay_amounts = [round(p[1], 2) for p in pay_totals_sorted]

    # ── Top 5 expenses ─────────────────────────────────────────────────────
    top_5 = month_expenses[:5]

    # ── Budget history for grouped bar (6 months) ──────────────────────────
    budget_history = get_budget_history(user_id, 6)
    bh_labels   = [item['month'] for item in reversed(budget_history)]
    bh_budgets  = [item['budget'] for item in reversed(budget_history)]
    bh_spending = [item['spending'] for item in reversed(budget_history)]

    # ── Calendar heatmap data ──────────────────────────────────────────────
    max_day_spend = max(daily_amounts) if daily_amounts else 1
    calendar_weeks = []
    first_weekday = cal_module.monthrange(sel_dt.year, sel_dt.month)[0]  # 0=Mon
    day_counter = 1
    week = [None] * first_weekday
    while day_counter <= days_in_month:
        week.append({
            'day': day_counter,
            'amount': daily_totals.get(day_counter, 0),
            'intensity': round(daily_totals.get(day_counter, 0) / max_day_spend, 2) if max_day_spend > 0 else 0
        })
        if len(week) == 7:
            calendar_weeks.append(week)
            week = []
        day_counter += 1
    if week:
        while len(week) < 7:
            week.append(None)
        calendar_weeks.append(week)

    # ── Avg daily spend ────────────────────────────────────────────────────
    avg_daily = total_this_month / active_days if active_days > 0 else 0

    return render_template('analytics.html',
        username=user.username,
        selected_month=selected_month,
        selected_month_label=sel_dt.strftime("%B %Y"),
        available_months=available_months,
        # Totals
        total_this_month=total_this_month,
        total_prev_month=total_prev_month,
        mom_change_pct=mom_change_pct,
        mom_direction=mom_direction,
        active_days=active_days,
        days_in_month=days_in_month,
        avg_daily=avg_daily,
        # Biggest
        biggest_expense=biggest_expense,
        peak_day=peak_day,
        peak_day_amount=peak_day_amount,
        # Top 5
        top_5=top_5,
        # Trend banner
        biggest_increase_cat=biggest_increase_cat,
        biggest_increase_amt=biggest_increase_amt,
        # Category chart
        cat_labels=cat_labels,
        cat_amounts=cat_amounts,
        cat_percentages=cat_percentages,
        cat_totals_sorted=cat_totals_sorted,
        # Daily chart
        daily_labels=daily_labels,
        daily_amounts=daily_amounts,
        # Payment chart
        pay_labels=pay_labels,
        pay_amounts=pay_amounts,
        # Budget history chart
        bh_labels=bh_labels,
        bh_budgets=bh_budgets,
        bh_spending=bh_spending,
        # Calendar
        calendar_weeks=calendar_weeks,
        sel_dt=sel_dt,
        current_date=datetime.now(),
    )


@app.route('/export/pdf')
def export_pdf():
    """
    Generate and stream a PDF expense report for the selected month.
    Uses ReportLab SimpleDocTemplate with Platypus for layout.
    Accepts ?month=YYYY-MM; defaults to current month.
    Returns the PDF as a file download attachment.
    """
    if not is_logged_in():
        flash('Please log in first.', 'error')
        return redirect(url_for('login'))

    import io, calendar as cal_mod
    from flask import make_response
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak
    )
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame

    user_id = session['user_id']
    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for('login'))

    # ── Month selection ──────────────────────────────────────────────────
    selected_month = request.args.get('month', get_current_year_month())
    try:
        sel_dt = datetime.strptime(selected_month, "%Y-%m")
    except ValueError:
        sel_dt = datetime.now()
        selected_month = sel_dt.strftime("%Y-%m")

    month_label = sel_dt.strftime("%B %Y")

    # ── Fetch data ───────────────────────────────────────────────────────
    month_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date.startswith(selected_month)
    ).order_by(Expense.date.desc()).all()

    all_expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc()).all()

    total_spent = sum(e.amount for e in month_expenses)
    budget = get_user_budget(user_id, selected_month)
    remaining = budget - total_spent

    cat_totals = {}
    for e in month_expenses:
        cat_totals[e.category] = cat_totals.get(e.category, 0) + e.amount
    cat_sorted = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)

    # ── Colours ──────────────────────────────────────────────────────────
    INDIGO      = colors.HexColor('#4F46E5')
    INDIGO_LIGHT= colors.HexColor('#EEF2FF')
    SLATE       = colors.HexColor('#64748B')
    DANGER      = colors.HexColor('#EF4444')
    SUCCESS     = colors.HexColor('#10B981')
    BLACK       = colors.HexColor('#1E293B')
    BORDER      = colors.HexColor('#E2E8F0')
    WHITE       = colors.white
    ROW_ALT     = colors.HexColor('#F8FAFC')

    # ── Styles ───────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()
    def style(name, **kw):
        s = ParagraphStyle(name, **kw)
        return s

    title_style   = style('Title2', fontName='Helvetica-Bold', fontSize=20, textColor=WHITE, alignment=TA_LEFT, spaceAfter=2)
    sub_style     = style('Sub',    fontName='Helvetica',      fontSize=9,  textColor=colors.HexColor('#CBD5E1'), alignment=TA_LEFT)
    section_style = style('Sec',    fontName='Helvetica-Bold', fontSize=11, textColor=BLACK,  spaceBefore=12, spaceAfter=6)
    body_style    = style('Body',   fontName='Helvetica',      fontSize=9,  textColor=SLATE)
    cell_style    = style('Cell',   fontName='Helvetica',      fontSize=8,  textColor=BLACK,  leading=12)
    cell_bold     = style('CellB',  fontName='Helvetica-Bold', fontSize=8,  textColor=BLACK,  leading=12)
    cell_right    = style('CellR',  fontName='Helvetica',      fontSize=8,  textColor=DANGER, leading=12, alignment=TA_RIGHT)
    head_style    = style('Head',   fontName='Helvetica-Bold', fontSize=8,  textColor=WHITE,  leading=12, alignment=TA_CENTER)
    small_style   = style('Small',  fontName='Helvetica',      fontSize=7,  textColor=SLATE,  alignment=TA_CENTER)

    # ── Build document in memory ─────────────────────────────────────────
    buffer = io.BytesIO()
    W, H = A4
    LEFT = RIGHT = TOP = BOTTOM = 18*mm

    # Page number footer callback
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(SLATE)
        page_text = f"ExpenseFlow  ·  Confidential  ·  Page {doc.page}"
        canvas.drawCentredString(W / 2, BOTTOM - 6*mm, page_text)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=LEFT, rightMargin=RIGHT,
        topMargin=TOP, bottomMargin=BOTTOM + 8*mm,
        title=f"ExpenseFlow Report – {month_label}",
        author=user.username,
    )

    story = []
    col_w = W - LEFT - RIGHT  # usable width

    # ── 1. Header Banner ─────────────────────────────────────────────────
    header_data = [[
        Paragraph(f"ExpenseFlow", title_style),
        Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}", sub_style),
    ]]
    header_table = Table(header_data, colWidths=[col_w * 0.65, col_w * 0.35])
    header_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,-1), INDIGO),
        ('TOPPADDING',  (0,0), (-1,-1), 14),
        ('BOTTOMPADDING',(0,0),(-1,-1), 14),
        ('LEFTPADDING', (0,0), (0,-1), 16),
        ('RIGHTPADDING',(-1,0),(-1,-1), 16),
        ('ALIGN',       (1,0), (1,0), 'RIGHT'),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6*mm))

    # ── 2. Report title + user info ──────────────────────────────────────
    story.append(Paragraph(f"Expense Report — {month_label}", section_style))
    info_data = [[
        Paragraph(f"<b>Account:</b> {user.username}", body_style),
        Paragraph(f"<b>Email:</b> {user.email}", body_style),
        Paragraph(f"<b>Period:</b> {month_label}", body_style),
    ]]
    info_table = Table(info_data, colWidths=[col_w/3]*3)
    info_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0),(-1,-1), INDIGO_LIGHT),
        ('TOPPADDING',  (0,0),(-1,-1), 8),
        ('BOTTOMPADDING',(0,0),(-1,-1), 8),
        ('LEFTPADDING', (0,0),(-1,-1), 10),
        ('BOX',         (0,0),(-1,-1), 0.5, BORDER),
        ('ROUNDEDCORNERS',[4,4,4,4]),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 5*mm))

    # ── 3. Summary Stats ─────────────────────────────────────────────────
    story.append(Paragraph("Summary", section_style))

    def stat_cell(label, value, color=BLACK):
        return [
            Paragraph(label, small_style),
            Paragraph(value, ParagraphStyle('sv', fontName='Helvetica-Bold', fontSize=14,
                                            textColor=color, alignment=TA_CENTER)),
        ]

    rem_color = SUCCESS if remaining >= 0 else DANGER
    stats_data = [
        [Paragraph("TOTAL SPENT", small_style),
         Paragraph("MONTHLY BUDGET", small_style),
         Paragraph("REMAINING", small_style),
         Paragraph("TRANSACTIONS", small_style)],
        [Paragraph(f"₹{total_spent:,.2f}", ParagraphStyle('sv1', fontName='Helvetica-Bold', fontSize=14, textColor=INDIGO, alignment=TA_CENTER)),
         Paragraph(f"₹{budget:,.2f}",      ParagraphStyle('sv2', fontName='Helvetica-Bold', fontSize=14, textColor=BLACK, alignment=TA_CENTER)),
         Paragraph(f"₹{abs(remaining):,.2f}", ParagraphStyle('sv3', fontName='Helvetica-Bold', fontSize=14, textColor=rem_color, alignment=TA_CENTER)),
         Paragraph(str(len(month_expenses)), ParagraphStyle('sv4', fontName='Helvetica-Bold', fontSize=14, textColor=SLATE, alignment=TA_CENTER))],
    ]
    stats_table = Table(stats_data, colWidths=[col_w/4]*4)
    stats_table.setStyle(TableStyle([
        ('BOX',          (0,0),(-1,-1), 0.5, BORDER),
        ('INNERGRID',    (0,0),(-1,-1), 0.5, BORDER),
        ('BACKGROUND',   (0,0),(-1,0), INDIGO_LIGHT),
        ('TOPPADDING',   (0,0),(-1,-1), 10),
        ('BOTTOMPADDING',(0,0),(-1,-1), 10),
        ('ALIGN',        (0,0),(-1,-1), 'CENTER'),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 5*mm))

    # ── 4. Category Breakdown ─────────────────────────────────────────────
    if cat_sorted:
        story.append(Paragraph("Category Breakdown", section_style))
        cat_head = [
            Paragraph("Category",   head_style),
            Paragraph("Amount",     head_style),
            Paragraph("% of Total", head_style),
        ]
        cat_rows = [cat_head]
        for i, (cat, amt) in enumerate(cat_sorted):
            pct = (amt / total_spent * 100) if total_spent > 0 else 0
            bg = ROW_ALT if i % 2 == 0 else WHITE
            cat_rows.append([
                Paragraph(cat,                    cell_style),
                Paragraph(f"₹{amt:,.2f}",         cell_bold),
                Paragraph(f"{pct:.1f}%",           cell_style),
            ])

        cat_table = Table(cat_rows, colWidths=[col_w*0.5, col_w*0.25, col_w*0.25])
        cat_style_rules = TableStyle([
            ('BACKGROUND',   (0,0),(-1,0), INDIGO),
            ('TEXTCOLOR',    (0,0),(-1,0), WHITE),
            ('BOX',          (0,0),(-1,-1), 0.5, BORDER),
            ('INNERGRID',    (0,0),(-1,-1), 0.3, BORDER),
            ('TOPPADDING',   (0,0),(-1,-1), 7),
            ('BOTTOMPADDING',(0,0),(-1,-1), 7),
            ('LEFTPADDING',  (0,0),(-1,-1), 10),
            ('ALIGN',        (1,0),(-1,-1), 'RIGHT'),
            ('ALIGN',        (0,0),(0,-1), 'LEFT'),
        ])
        for i in range(1, len(cat_rows)):
            if i % 2 == 0:
                cat_style_rules.add('BACKGROUND', (0,i), (-1,i), ROW_ALT)
        cat_table.setStyle(cat_style_rules)
        story.append(cat_table)
        story.append(Spacer(1, 5*mm))

    # ── 5. Expense List ───────────────────────────────────────────────────
    target = month_expenses if month_expenses else all_expenses[:50]
    label_scope = month_label if month_expenses else "All Time (latest 50)"
    story.append(Paragraph(f"Expense List — {label_scope}", section_style))

    exp_head = [
        Paragraph("Date",           head_style),
        Paragraph("Category",       head_style),
        Paragraph("Description",    head_style),
        Paragraph("Method",         head_style),
        Paragraph("Amount",         head_style),
    ]
    exp_rows = [exp_head]
    for i, e in enumerate(target):
        desc = (e.description or '—')[:45]
        exp_rows.append([
            Paragraph(e.date,                   cell_style),
            Paragraph(e.category,               cell_style),
            Paragraph(desc,                     cell_style),
            Paragraph(e.payment_method or '—',  cell_style),
            Paragraph(f"₹{e.amount:,.2f}",      cell_right),
        ])

    # Total row
    exp_rows.append([
        Paragraph("", cell_style),
        Paragraph("", cell_style),
        Paragraph("", cell_style),
        Paragraph("TOTAL", cell_bold),
        Paragraph(f"₹{sum(e.amount for e in target):,.2f}",
                  ParagraphStyle('tot', fontName='Helvetica-Bold', fontSize=8,
                                 textColor=INDIGO, alignment=TA_RIGHT)),
    ])

    col_widths = [col_w*0.13, col_w*0.18, col_w*0.35, col_w*0.16, col_w*0.18]
    exp_table = Table(exp_rows, colWidths=col_widths, repeatRows=1)
    exp_style = TableStyle([
        ('BACKGROUND',    (0,0),(-1,0), INDIGO),
        ('TEXTCOLOR',     (0,0),(-1,0), WHITE),
        ('BOX',           (0,0),(-1,-1), 0.5, BORDER),
        ('INNERGRID',     (0,0),(-1,-1), 0.3, BORDER),
        ('TOPPADDING',    (0,0),(-1,-1), 6),
        ('BOTTOMPADDING', (0,0),(-1,-1), 6),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
        ('ALIGN',         (4,0),(-1,-1), 'RIGHT'),
        # Total row highlight
        ('BACKGROUND',    (0,-1),(-1,-1), INDIGO_LIGHT),
        ('LINEABOVE',     (0,-1),(-1,-1), 1, INDIGO),
    ])
    for i in range(1, len(exp_rows) - 1):
        if i % 2 == 0:
            exp_style.add('BACKGROUND', (0,i), (-1,i), ROW_ALT)
    exp_table.setStyle(exp_style)
    story.append(exp_table)

    # ── Build PDF ────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)

    filename = f"ExpenseFlow_Report_{sel_dt.strftime('%B_%Y')}.pdf"
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


