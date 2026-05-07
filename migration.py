#!/usr/bin/env python3
"""One-time migration script from txt files to SQLite"""
import sqlite3
import glob
import os
from models import DatabaseManager
from datetime import datetime

def migrate():
    db = DatabaseManager()
    
    print("Starting migration...")
    
    # Users migration
    users_file = 'users.txt'
    if os.path.exists(users_file):
        with open(users_file, 'r') as f:
            conn = sqlite3.connect(db.db_path)
            c = conn.cursor()
            migrated = 0
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 5:
                    username, email, hashed_pw, user_id_str, reg_date = parts[:5]
                    user_id = int(user_id_str)
                    c.execute("INSERT OR IGNORE INTO users (username, email, hashed_password, registration_date, id) VALUES (?, ?, ?, ?, ?)", 
                             (username, email, hashed_pw, reg_date, user_id))
                    migrated += 1
            conn.commit()
            conn.close()
            print(f"Migrated {migrated} users")
    else:
        print("users.txt not found, skipping users migration")

    # Expenses migration
    expense_files = glob.glob('user_*_expenses.txt')
    total_expenses = 0
    for file in expense_files:
        user_id = int(file.split('_')[1].split('_')[0])
        try:
            with open(file, 'r') as f:
                conn = sqlite3.connect(db.db_path)
                c = conn.cursor()
                migrated_exp = 0
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 4:
                        date, category, amount, *rest = parts
                        desc = rest[0] if rest else ''
                        pm = rest[1] if len(rest) > 1 else ''
                        c.execute("INSERT INTO expenses (user_id, date, category, amount, description, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                                 (user_id, date, category, float(amount), desc, pm))
                        migrated_exp += 1
                total_expenses += migrated_exp
                conn.commit()
                conn.close()
                print(f"Migrated {migrated_exp} expenses from {file}")
        except Exception as e:
            print(f"Error migrating {file}: {e}")

    # Budgets (simplified)
    budget_files = glob.glob('user_*_budget_*.txt') + glob.glob('user_*_recurring_budget.txt')
    migrated_budgets = 0
    for file in budget_files:
        user_id_str = file.split('_')[1]
        if 'recurring' in file:
            ym = datetime.now().strftime('%Y-%m')  # apply to current
            amount = float(open(file).read().strip())
            conn = sqlite3.connect(db.db_path)
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO budgets (user_id, year_month, amount, is_recurring) VALUES (?, ?, ?, 1)", (int(user_id_str), ym, amount))
            conn.commit()
            conn.close()
            migrated_budgets += 1
        else:
            ym = file.split('_budget_')[1].split('.')[0]
            amount = float(open(file).read().strip())
            conn = sqlite3.connect(db.db_path)
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO budgets (user_id, year_month, amount) VALUES (?, ?, ?)", (int(user_id_str), ym, amount))
            conn.commit()
            conn.close()
            migrated_budgets += 1
    
    print(f"Total: {total_expenses} expenses, {migrated_budgets} budgets migrated")
    print("Migration complete! Ready to delete txt files? Run: rm user_*_*")

if __name__ == '__main__':
    migrate()

