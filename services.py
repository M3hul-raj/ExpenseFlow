from models import User, Expense
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
import random
from typing import Dict, List, Tuple

import sqlite3

class ExpenseService:
    def __init__(self):
        pass

    def get_user_expenses(self, user_id: int) -> List[Expense]:
        """Get all expenses for user"""
        conn = sqlite3.connect(self.db.db_path)
        df = pd.read_sql_query("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC", conn, params=(user_id,))
        conn.close()
        return [Expense(**row._asdict()) for _, row in df.iterrows()]

    def add_expense(self, user_id: int, expense_data: Dict) -> bool:
        """Add new expense"""
        conn = sqlite3.connect(self.db.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO expenses (user_id, date, category, amount, description, payment_method)
                     VALUES (?, ?, ?, ?, ?, ?)''', 
                 (user_id, expense_data['date'], expense_data['category'], 
                  float(expense_data['amount']), expense_data.get('description', ''), 
                  expense_data.get('payment_method', '')))
        conn.commit()
        conn.close()
        return c.rowcount > 0

    def get_dashboard_stats(self, user_id: int) -> Dict:
        """Dashboard metrics + chart data"""
        conn = sqlite3.connect(self.db.db_path)
        
        # Total spent, expense count
        df = pd.read_sql_query("SELECT * FROM expenses WHERE user_id = ?", conn, params=(user_id,))
        total_spent = df['amount'].sum()
        expense_count = len(df)
        
        # Category totals for pie chart
        cat_df = df.groupby('category')['amount'].sum().reset_index()
        categories = cat_df['category'].tolist()
        category_amounts = cat_df['amount'].tolist()
        
        # Monthly trend (last 6 months)
        df['year_month'] = pd.to_datetime(df['date']).dt.to_period('M').astype(str)
        monthly_df = df.groupby('year_month')['amount'].sum().tail(6).reset_index()
        months = monthly_df['year_month'].tolist()
        monthly_amounts = monthly_df['amount'].tolist()
        
        # Current month spending
        current_month = datetime.now().strftime('%Y-%m')
        current_spent = df[df['year_month'] == current_month]['amount'].sum() if current_month in df['year_month'].values else 0
        
        # Daily average
        df['date_only'] = pd.to_datetime(df['date']).dt.date
        unique_dates = df['date_only'].nunique()
        avg_daily = total_spent / max(1, unique_dates)
        
        conn.close()
        
        # Budget from BudgetService
        budget_service = BudgetService()
        budget = budget_service.get_user_budget(user_id)
        budget_progress = (current_spent / budget * 100) if budget > 0 else 0
        
        return {
            'total_spent': total_spent,
            'expense_count': expense_count,
            'avg_daily_spend': avg_daily,
            'current_month_spent': current_spent,
            'budget': budget,
            'budget_progress': budget_progress,
            'categories': categories,
            'category_amounts': category_amounts,
            'months': months,
            'monthly_amounts': monthly_amounts
        }

    def get_summary_stats(self, user_id: int) -> Dict:
        """Summary page stats"""
        conn = sqlite3.connect(self.db.db_path)
        df = pd.read_sql_query("SELECT * FROM expenses WHERE user_id = ?", conn, params=(user_id,))
        conn.close()
        
        # Category totals
        category_totals = df.groupby('category')['amount'].sum().to_dict()
        
        # Monthly totals
        df['year_month'] = pd.to_datetime(df['date']).dt.to_period('M').astype(str)
        monthly_totals = df.groupby('year_month')['amount'].sum().to_dict()
        
        # Payment method totals
        df['payment_method'] = df['payment_method'].fillna('N/A')
        payment_totals = df.groupby('payment_method')['amount'].sum().to_dict()
        
        top_category = max(category_totals, key=category_totals.get) if category_totals else None
        df['date_only'] = pd.to_datetime(df['date']).dt.date
        avg_daily = df['amount'].sum() / df['date_only'].nunique()
        
        return {
            'category_totals': dict(sorted(category_totals.items(), key=lambda x: x[1], reverse=True)),
            'monthly_totals': dict(sorted(monthly_totals.items())),
            'payment_method_totals': payment_totals,
            'avg_daily_spend': avg_daily,
            'top_category': top_category
        }

class BudgetService:
    def __init__(self):
        self.db = DatabaseManager()

    def get_user_budget(self, user_id: int, year_month: str = None) -> float:
        """Get user budget for specific month or current"""
        conn = sqlite3.connect(self.db.db_path)
        if year_month is None:
            year_month = datetime.now().strftime('%Y-%m')
        c = conn.cursor()
        c.execute("SELECT amount FROM budgets WHERE user_id = ? AND year_month = ? LIMIT 1", (user_id, year_month))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 2000.0  # default

    def set_budget(self, user_id: int, year_month: str, amount: float, recurring: bool = False) -> bool:
        conn = sqlite3.connect(self.db.db_path)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO budgets (user_id, year_month, amount, is_recurring)
                     VALUES (?, ?, ?, ?)''', (user_id, year_month, amount, int(recurring)))
        conn.commit()
        conn.close()
        return True

    def get_budget_history(self, user_id: int, months: int = 6) -> List[Dict]:
        """Budget vs actual for last N months"""
        conn = sqlite3.connect(self.db.db_path)
        df_exp = pd.read_sql_query("SELECT * FROM expenses WHERE user_id = ?", conn, params=(user_id,))
        df_exp['year_month'] = pd.to_datetime(df_exp['date']).dt.to_period('M').astype(str)
        monthly_spend = df_exp.groupby('year_month')['amount'].sum().to_dict()
        conn.close()
        
        history = []
        now = datetime.now()
        for i in range(months):
            ym = (now - relativedelta(months=i)).strftime('%Y-%m')
            budget = self.get_user_budget(user_id, ym)
            spend = monthly_spend.get(ym, 0)
            status = "On Track" if spend <= budget * 0.9 else "Near Limit" if spend <= budget else "Over Budget"
            history.append({
                'year_month': ym,
                'budget': budget,
                'spending': spend,
                'status': status
            })
        return history

class SmartInsightsService:
    def __init__(self):
        self.expense_service = ExpenseService()

    def get_ai_insights(self, user_id: int) -> List[str]:
        """Generate smart insights"""
        stats = self.expense_service.get_summary_stats(user_id)
        insights = []
        
        if stats['total_spent'] > 5000:
            insights.append("You're spending more than average - consider reviewing subscriptions!")
        
        top_cat = stats['top_category']
        if top_cat:
            insights.append(f"Top spending category: {top_cat}")
        
        # Random tip
        tips = [
            "Cook at home 3x/week to save ₹2000/month",
            "Review unused subscriptions (Netflix/Spotify)",
            "Use cashback cards for groceries (5-10% savings)",
            "Track small expenses - they add up!",
            "Plan weekly budgets per category"
        ]
        insights.append(random.choice(tips))
        
        return insights[:3]

# Global instances (disabled for SQLite migration)
# expense_service = ExpenseService()
# budget_service = BudgetService()
# insights_service = SmartInsightsService()

