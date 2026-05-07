import hashlib
# pyrefly: ignore [missing-import]
from flask import Flask, render_template, request, redirect, session, flash, url_for
from datetime import datetime
import random, os
from dateutil.relativedelta import relativedelta
import sqlite3

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

DATA_FILE = "expenses.txt"
TIPS_FILE = "tips.txt"
USERS_FILE = "users.txt"

# Ensure files exist
if not os.path.exists(DATA_FILE):
    open(DATA_FILE, 'w').close()

if not os.path.exists(TIPS_FILE):
    with open(TIPS_FILE, 'w') as f:
        f.write("Cook at home instead of eating out.\n")
        f.write("Track your subscriptions.\n")
        f.write("Plan weekly budgets.\n")
        f.write("Use public transport to save fuel.\n")
        f.write("Avoid unnecessary online purchases.\n")

if not os.path.exists(USERS_FILE):
    open(USERS_FILE, 'w').close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def is_logged_in():
    return 'user_id' in session

def get_user_data_file(user_id):
    return f"user_{user_id}_expenses.txt"

def get_user_budget_file(user_id, year_month=None):
    if year_month:
        return f"user_{user_id}_budget_{year_month}.txt"
    else:
        # For backward compatibility, check for old single budget file
        old_file = f"user_{user_id}_budget.txt"
        if os.path.exists(old_file):
            return old_file
        return f"user_{user_id}_budget_{get_current_year_month()}.txt"

def get_user_recurring_budget_file(user_id):
    return f"user_{user_id}_recurring_budget.txt"

def get_recurring_budget(user_id):
    recurring_file = get_user_recurring_budget_file(user_id)
    try:
        with open(recurring_file, 'r') as f:
            return float(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None

def set_recurring_budget(user_id, amount):
    recurring_file = get_user_recurring_budget_file(user_id)
    with open(recurring_file, 'w') as f:
        f.write(str(amount))

def get_budget_history(user_id, months=6):
    """Get budget and spending data for last N months"""
    from datetime import datetime
    import calendar

    history = []
    current_date = datetime.now()

    for i in range(months):
        date = current_date - relativedelta(months=i)
        year_month = date.strftime("%Y-%m")

        budget = get_user_budget(user_id, year_month)
        spending = get_monthly_spending(user_id, year_month)

        status = "On Track"
        if spending > budget:
            status = "Over Budget"
        elif spending > budget * 0.9:
            status = "Near Limit"

        history.append({
            'month': f"{calendar.month_name[date.month]} {date.year}",
            'year_month': year_month,
            'budget': budget,
            'spending': spending,
            'status': status,
            'remaining': budget - spending
        })

    return history

def get_monthly_spending(user_id, year_month):
    """Get total spending for a specific month"""
    user_file = get_user_data_file(user_id)
    total = 0.0

    try:
        with open(user_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    expense_date = parts[0]
                    try:
                        expense_year_month = expense_date[:7]  # YYYY-MM format
                        if expense_year_month == year_month:
                            total += float(parts[2])
                    except (ValueError, IndexError):
                        pass
    except FileNotFoundError:
        pass

    return total

def get_current_year_month():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m")

def get_user_budget(user_id, year_month=None):
    budget_file = get_user_budget_file(user_id, year_month)
    try:
        with open(budget_file, 'r') as f:
            return float(f.read().strip())
    except (FileNotFoundError, ValueError):
        # Check if recurring budget is set
        recurring_budget = get_recurring_budget(user_id)
        if recurring_budget is not None:
            return recurring_budget
        return 2000.0  # Default budget

def apply_filters(expenses, filters):
    """Apply all filters to expenses list. Returns filtered list."""
    filtered = expenses[:]
    
    # Keyword search in description (case insensitive)
    keyword = filters.get('keyword', '').strip().lower()
    if keyword:
        filtered = [e for e in filtered if keyword in e[3].lower()]
    
    # Category filter
    category = filters.get('category', '').strip()
    if category and category != 'All Categories':
        filtered = [e for e in filtered if e[1] == category]
    
    # Month filter (YYYY-MM)
    month = filters.get('month', '').strip()
    if month and month != 'All Months':
        filtered = [e for e in filtered if e[0][:7] == month]
    
    # Payment method filter
    payment_method = filters.get('payment_method', '').strip()
    if payment_method and payment_method != 'All Payment Methods':
        filtered = [e for e in filtered if e[4] == payment_method]
    
    # Date range
    from_date = filters.get('from_date', '').strip()
    to_date = filters.get('to_date', '').strip()
    if from_date:
        filtered = [e for e in filtered if e[0] >= from_date]
    if to_date:
        filtered = [e for e in filtered if e[0] <= to_date]
    
    # Amount range
    try:
        min_amount = float(filters.get('min_amount', 0))
        max_amount_str = filters.get('max_amount', '').strip()
        max_amount = float(max_amount_str) if max_amount_str and max_amount_str != 'No limit' else float('inf')
        
        filtered = [e for e in filtered if min_amount <= float(e[2]) <= max_amount]
    except ValueError:
        pass  # Invalid amounts, skip filter
    
    # Always sort newest first
    filtered.sort(key=lambda x: x[0], reverse=True)
    
    return filtered

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

        # Server-side validation
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('register'))

        # Check if user already exists
        with open(USERS_FILE, 'r') as f:
            for line in f:
                try:
                    parts = line.strip().split(',')
                    stored_username = parts[0]
                    if stored_username == username:
                        flash('Username already exists. Please choose a different one.', 'error')
                        return redirect(url_for('register'))
                except ValueError:
                    continue  # Skip invalid lines

        # Create new user
        user_id = str(random.randint(10000, 99999))
        hashed_password = hash_password(password)
        registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(USERS_FILE, 'a') as f:
            f.write(f"{username},{email},{hashed_password},{user_id},{registration_date}\n")

        # Create user-specific expense file
        user_file = get_user_data_file(user_id)
        open(user_file, 'w').close()

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

        with open(USERS_FILE, 'r') as f:
            for line in f:
                try:
                    parts = line.strip().split(',')
                    if len(parts) >= 4:
                        stored_username = parts[0]
                        email = parts[1]
                        hashed_password = parts[2]
                        user_id = parts[3]
                        if (stored_username == username_or_email or email == username_or_email) and verify_password(password, hashed_password):
                            session['user_id'] = user_id
                            session['username'] = stored_username
                            session['email'] = email
                            flash('Login successful!', 'success')
                            return redirect(url_for('dashboard'))
                except ValueError:
                    continue  # Skip invalid lines

        flash('User does not exist. Please sign up first!', 'error')
        return redirect(url_for('register'))

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
    user_file = get_user_data_file(user_id)

    # Get user registration date
    registration_date = None
    with open(USERS_FILE, 'r') as f:
        for line in f:
            try:
                stored_username, stored_email, hashed_password, stored_user_id, reg_date = line.strip().split(',')
                if stored_user_id == user_id:
                    registration_date = reg_date
                    break
            except ValueError:
                continue

    # Ensure user file exists
    if not os.path.exists(user_file):
        open(user_file, 'w').close()

    expenses = []
    total_spent = 0.0
    category_totals = {}
    monthly_totals = {}

    with open(user_file, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 4:
                if len(parts) == 4:
                    parts.append('')
                expenses.append(parts)
                try:
                    amount = float(parts[2])
                    total_spent += amount

                    category = parts[1]
                    category_totals[category] = category_totals.get(category, 0) + amount

                    try:
                        date_parts = parts[0].split('-')
                        if len(date_parts) >= 2:
                            month_key = f"{date_parts[0]}-{date_parts[1]}"
                            monthly_totals[month_key] = monthly_totals.get(month_key, 0) + amount
                    except:
                        pass

                except ValueError:
                    pass

    expenses.sort(key=lambda x: x[0], reverse=True)

    unique_dates = set(e[0] for e in expenses)
    avg_daily_spend = total_spent / max(1, len(unique_dates))
    top_category = max(category_totals, key=category_totals.get) if category_totals else 'None'

    current_year_month = get_current_year_month()
    budget = get_user_budget(user_id, current_year_month)
    recurring_budget = get_recurring_budget(user_id)

    current_month_spent = 0.0
    for e in expenses:
        try:
            if e[0][:7] == current_year_month:
                current_month_spent += float(e[2])
        except:
            pass

    budget_progress = (current_month_spent / budget) * 100 if budget > 0 else 0

    categories = list(category_totals.keys())
    category_amounts = list(category_totals.values())
    months = sorted(list(monthly_totals.keys()), reverse=True)[-6:]
    monthly_amounts = [monthly_totals.get(m, 0) for m in months]

    budget_history = get_budget_history(user_id, 6)
    budget_chart_labels = [item['month'] for item in budget_history]
    budget_chart_budgets = [item['budget'] for item in budget_history]
    budget_chart_spending = [item['spending'] for item in budget_history]

    # Add budget alerts
    if budget_progress >= 100:
        flash('⚠️ You have exceeded your monthly budget!', 'error')
    elif budget_progress >= 80:
        flash('⚠️ You are approaching your budget limit (80% used).', 'warning')

    current_date = datetime.now()

    return render_template('dashboard.html',
                         expenses=expenses,
                         username=session['username'],
                         email=session['email'],
                         registration_date=registration_date,
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
                         current_date=current_date)

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
        user_file = get_user_data_file(user_id)

        with open(user_file, 'a') as f:
            f.write(f"{date},{category},{amount},{description},{payment_method}\n")

        flash('Expense added successfully!', 'success')
        return redirect(url_for('dashboard'))

    current_date = datetime.now()

    return render_template('add_expense_updated.html', current_date=current_date)

@app.route('/view')
def view_expense():
    if not is_logged_in():
        flash('Please log in to view expenses.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_file = get_user_data_file(user_id)

    expenses = []
    total_spent = 0.0
    category_totals = {}
    monthly_totals = {}
    payment_method_totals = {}

    with open(user_file, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 4:  # Changed to >= 4 to handle new payment_method field
                # Handle backward compatibility - if no payment_method, add empty string
                if len(parts) == 4:
                    parts.append('')
                expenses.append(parts)
                try:
                    amount = float(parts[2])
                    total_spent += amount

                    # Category totals
                    category = parts[1]
                    category_totals[category] = category_totals.get(category, 0) + amount

                    # Payment method totals
                    payment_method = parts[4] if parts[4] else 'N/A'
                    payment_method_totals[payment_method] = payment_method_totals.get(payment_method, 0) + amount

                    # Monthly totals (assuming date format YYYY-MM-DD)
                    try:
                        date_parts = parts[0].split('-')
                        if len(date_parts) >= 2:
                            month_key = f"{date_parts[0]}-{date_parts[1]}"
                            monthly_totals[month_key] = monthly_totals.get(month_key, 0) + amount
                    except:
                        pass

                except ValueError:
                    pass  # Skip invalid amounts

    # Sort expenses by date (newest first)
    expenses.sort(key=lambda x: x[0], reverse=True)

    # Calculate additional metrics
    unique_dates = set(expense[0] for expense in expenses)
    avg_daily_spend = total_spent / max(1, len(unique_dates))
    top_category = max(category_totals, key=category_totals.get) if category_totals else 'None'
    top_payment_method = max(payment_method_totals, key=payment_method_totals.get) if payment_method_totals else 'None'

    # Sort category totals by amount (descending)
    sorted_category_totals = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)

    # Sort monthly totals by month (descending)
    sorted_monthly_totals = sorted(monthly_totals.items(), key=lambda x: x[0], reverse=True)

    # Sort payment method totals by amount (descending)
    sorted_payment_method_totals = sorted(payment_method_totals.items(), key=lambda x: x[1], reverse=True)

    # Get a random savings tip
    import random
    with open(TIPS_FILE, 'r') as f:
        tips = f.readlines()
    savings_tip = random.choice(tips).strip() if tips else "Track your expenses regularly!"

    current_date = datetime.now()

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
                         current_date=current_date)

@app.route('/edit/<int:expense_index>', methods=['GET', 'POST'])
def edit_expense(expense_index):
    if not is_logged_in():
        flash('Please log in to edit expenses.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_file = get_user_data_file(user_id)

    expenses = []
    with open(user_file, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 4:  # Changed to >= 4 to handle new payment_method field
                # Handle backward compatibility - if no payment_method, add empty string
                if len(parts) == 4:
                    parts.append('')
                expenses.append(parts)

    if not (0 <= expense_index < len(expenses)):
        flash('Invalid expense index.', 'error')
        return redirect(url_for('view_expense'))

    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = request.form['amount']
        description = request.form['description']
        payment_method = request.form['payment_method']

        # Update the expense
        expenses[expense_index] = [date, category, amount, description, payment_method]

        # Write back to file
        with open(user_file, 'w') as f:
            for expense in expenses:
                f.write(','.join(expense) + '\n')

        flash('Expense updated successfully!', 'success')
        return redirect(url_for('view_expense'))

    # GET request - show edit form with current data
    expense = expenses[expense_index]
    return render_template('edit_expense.html', expense=expense, expense_index=expense_index)

@app.route('/delete/<int:expense_index>')
def delete_expense(expense_index):
    if not is_logged_in():
        flash('Please log in to delete expenses.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_file = get_user_data_file(user_id)

    expenses = []
    with open(user_file, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 4:  # Changed to >= 4 to handle new payment_method field
                # Handle backward compatibility - if no payment_method, add empty string
                if len(parts) == 4:
                    parts.append('')
                expenses.append(parts)

    if 0 <= expense_index < len(expenses):
        expenses.pop(expense_index)
        with open(user_file, 'w') as f:
            for expense in expenses:
                f.write(','.join(expense) + '\n')
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
            new_budget = float(request.form['budget'])

            if new_budget <= 0:
                flash('Budget must be a positive number.', 'error')
                return redirect(url_for('set_budget'))

            budget_file = get_user_budget_file(user_id, year_month)
            with open(budget_file, 'w') as f:
                f.write(str(new_budget))

            # Check if recurring budget is set
            if 'recurring' in request.form:
                set_recurring_budget(user_id, new_budget)
                flash(f'Recurring budget set to ₹{new_budget:.2f}! This will be applied to future months.', 'success')
            else:
                flash(f'Budget for {month}/{year} updated successfully!', 'success')

            return redirect(url_for('dashboard'))

        except ValueError:
            flash('Please enter a valid budget amount.', 'error')
            return redirect(url_for('set_budget'))

    from datetime import datetime
    current_month = datetime.now().strftime("%m")
    current_year = datetime.now().year

    return render_template('set_budget.html',
                         current_budget=current_budget,
                         current_month=current_month,
                         current_year=current_year)

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

        # Get current budget
        current_budget = get_user_budget(user_id, current_year_month)

        # Calculate new budget
        if adjustment_type == 'increase':
            new_budget = current_budget + adjustment_amount
            message = f'Budget increased by ₹{adjustment_amount:.2f}! New budget: ₹{new_budget:.2f}'
        elif adjustment_type == 'decrease':
            new_budget = max(0, current_budget - adjustment_amount)
            message = f'Budget decreased by ₹{adjustment_amount:.2f}! New budget: ₹{new_budget:.2f}'
        else:
            flash('Invalid adjustment type.', 'error')
            return redirect(url_for('dashboard'))

        # Save new budget
        budget_file = get_user_budget_file(user_id, current_year_month)
        with open(budget_file, 'w') as f:
            f.write(str(new_budget))

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

        # Get current budget
        current_budget = get_user_budget(user_id, current_year_month)

        # Calculate new budget
        if action == 'add':
            new_budget = current_budget + quick_amount
        elif action == 'subtract':
            new_budget = max(0, current_budget - quick_amount)
        else:
            flash('Invalid action.', 'error')
            return redirect(url_for('dashboard'))

        # Save new budget
        budget_file = get_user_budget_file(user_id, current_year_month)
        with open(budget_file, 'w') as f:
            f.write(str(new_budget))

        flash(f'Budget adjusted by ₹{quick_amount:.2f}! New budget: ₹{new_budget:.2f}', 'success')
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
    username = session['username']
    email = session['email']

    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        # Verify current password
        with open(USERS_FILE, 'r') as f:
            for line in f:
                try:
                    stored_username, stored_email, hashed_password, stored_user_id, registration_date = line.strip().split(',')
                    if stored_user_id == user_id:
                        if not verify_password(current_password, hashed_password):
                            flash('Current password is incorrect.', 'error')
                            return redirect(url_for('edit_profile'))
                        break
                except ValueError:
                    continue

        # Check if new username already exists (if changed)
        if new_username != username:
            with open(USERS_FILE, 'r') as f:
                for line in f:
                    try:
                        stored_username, _, _, _, _ = line.strip().split(',')
                        if stored_username == new_username:
                            flash('Username already exists. Please choose a different one.', 'error')
                            return redirect(url_for('edit_profile'))
                    except ValueError:
                        continue

        # Validate new password if provided
        if new_password:
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('edit_profile'))
            if len(new_password) < 6:
                flash('New password must be at least 6 characters long.', 'error')
                return redirect(url_for('edit_profile'))

        # Update user data
        updated_lines = []
        with open(USERS_FILE, 'r') as f:
            for line in f:
                try:
                    stored_username, stored_email, hashed_password, stored_user_id, registration_date = line.strip().split(',')
                    if stored_user_id == user_id:
                        # Update fields
                        updated_username = new_username
                        updated_email = new_email
                        updated_password = hash_password(new_password) if new_password else hashed_password
                        updated_line = f"{updated_username},{updated_email},{updated_password},{stored_user_id},{registration_date}\n"
                        updated_lines.append(updated_line)
                    else:
                        updated_lines.append(line)
                except ValueError:
                    updated_lines.append(line)

        # Write back to file
        with open(USERS_FILE, 'w') as f:
            f.writelines(updated_lines)

        # Update session
        session['username'] = new_username
        session['email'] = new_email

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_profile.html', username=username, email=email)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
