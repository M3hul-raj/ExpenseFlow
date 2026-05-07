from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    expenses = db.relationship('Expense', backref='user', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    payment_method = db.Column(db.String(50), default='Cash')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Expense {self.category}: ₹{self.amount}>'

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    year_month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    amount = db.Column(db.Float, nullable=False)
    is_recurring = db.Column(db.Boolean, default=False)

import sqlite3

class DatabaseManager:
    def __init__(self, db_path='expenses.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY,
                      username TEXT UNIQUE NOT NULL,
                      email TEXT UNIQUE NOT NULL,
                      password_hash TEXT NOT NULL,
                      created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        # Expenses table
        c.execute('''CREATE TABLE IF NOT EXISTS expenses
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER NOT NULL,
                      date TEXT NOT NULL,
                      category TEXT NOT NULL,
                      amount REAL NOT NULL,
                      description TEXT,
                      payment_method TEXT DEFAULT 'Cash',
                      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (user_id) REFERENCES users (id))''')
        
        # Budgets table
        c.execute('''CREATE TABLE IF NOT EXISTS budgets
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER NOT NULL,
                      year_month TEXT NOT NULL,
                      amount REAL NOT NULL,
                      is_recurring INTEGER DEFAULT 0,
                      FOREIGN KEY (user_id) REFERENCES users (id),
                      UNIQUE(user_id, year_month))''')
        
        conn.commit()
        conn.close()

