import hashlib
from flask import Flask, render_template, request, redirect, session, flash, url_for
from datetime import datetime
import random, os
from dateutil.relativedelta import relativedelta
from models import db, User, Expense, Budget

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

app.secret_key = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

# Static tips to replace TIPS_FILE
TIPS = [
    "Cook at home instead of eating out.",
    "Track your subscriptions.",
    "Plan weekly budgets.",
    "Use public transport to save fuel.",
    "Avoid unnecessary online purchases."
]

def is_logged_in():
    return 'user_id' in session

def get_current_year_month():
    return datetime.now().strftime("%Y-%m")

def get_user_budget(user_id, year_month=None):
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
    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date.startswith(year_month)
    ).all()
    return sum(e.amount for e in expenses)

def get_budget_history(user_id, months=6):
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
    expenses = Expense.query.filter_by(user_id=user_id).all()
    expenses.sort(key=lambda x: x.date, reverse=True)
    return expenses

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

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

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username_or_email = request.form['username']
        password = request.form['password']

        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['email'] = user.email
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))

        if not user:
            flash('User does not exist. Please sign up first!', 'error')
            return redirect(url_for('register'))
        else:
            flash('Invalid password. Please try again!', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
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
    months = sorted(list(monthly_totals.keys()), reverse=True)[:6]
    months.reverse() # chronologically
    monthly_amounts = [monthly_totals.get(m, 0) for m in months]

    budget_history = get_budget_history(user_id, 6)
    budget_chart_labels = [item['month'] for item in budget_history]
    budget_chart_budgets = [item['budget'] for item in budget_history]
    budget_chart_spending = [item['spending'] for item in budget_history]

    if budget_progress >= 100:
        flash('⚠️ You have exceeded your monthly budget!', 'error')
    elif budget_progress >= 80:
        flash('⚠️ You are approaching your budget limit (80% used).', 'warning')

    return render_template('dashboard.html',
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
    if not is_logged_in():
        flash('Please log in to add expenses.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = request.form['amount']
        description = request.form['description']
        payment_method = request.form['payment_method']

        user_id = session['user_id']
        
        new_expense = Expense(
            user_id=user_id,
            date=date,
            category=category,
            amount=float(amount),
            description=description,
            payment_method=payment_method
        )
        db.session.add(new_expense)
        db.session.commit()

        flash('Expense added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_expense_updated.html', current_date=datetime.now())

@app.route('/view')
def view_expense():
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
        expense_to_edit.date = request.form['date']
        expense_to_edit.category = request.form['category']
        expense_to_edit.amount = float(request.form['amount'])
        expense_to_edit.description = request.form['description']
        expense_to_edit.payment_method = request.form['payment_method']
        
        db.session.commit()

        flash('Expense updated successfully!', 'success')
        return redirect(url_for('view_expense'))

    expense_list = [expense_to_edit.date, expense_to_edit.category, str(expense_to_edit.amount), expense_to_edit.description, expense_to_edit.payment_method]
    return render_template('edit_expense.html', expense=expense_list, expense_index=expense_index)

@app.route('/delete/<int:expense_index>')
def delete_expense(expense_index):
    if not is_logged_in():
        flash('Please log in to delete expenses.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    expenses_obj = get_user_expenses_sorted(user_id)

    if 0 <= expense_index < len(expenses_obj):
        expense_to_delete = expenses_obj[expense_index]
        db.session.delete(expense_to_delete)
        db.session.commit()
        flash('Expense deleted successfully!', 'success')
    else:
        flash('Invalid expense index.', 'error')

    return redirect(url_for('view_expense'))

@app.route('/set_budget', methods=['GET', 'POST'])
def set_budget():
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
