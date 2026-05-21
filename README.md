<p align="center">
  <img src="static/icons/icon-192x192.png" alt="ExpenseFlow Logo" width="80" height="80" style="border-radius: 16px;">
</p>

<h1 align="center">ExpenseFlow</h1>

<p align="center">
  <strong>A premium, full-stack personal finance tracker built with Flask</strong><br>
  Track expenses · Set budgets · Analyze spending · Export reports · Install as PWA
</p>

<p align="center">
  <a href="https://m3hulraj.pythonanywhere.com"><strong>🌐 Live Demo</strong></a> &nbsp;·&nbsp;
  <a href="#features"><strong>Features</strong></a> &nbsp;·&nbsp;
  <a href="#tech-stack"><strong>Tech Stack</strong></a> &nbsp;·&nbsp;
  <a href="#setup"><strong>Setup</strong></a>
</p>

---

## What is ExpenseFlow?

ExpenseFlow is a production-grade personal finance management application designed with a modern **fintech aesthetic**. It goes far beyond basic expense tracking — offering real-time budget alerts, 9-section analytics dashboards, PDF report generation, and Progressive Web App support for mobile installation.

Built as a full-stack Flask application with SQLAlchemy ORM, it features server-side input validation, indexed database queries, comprehensive error handling, and session-based authentication with hashed passwords.

---

## Features

### Core — Expense Management
- **Add Expenses** — Quick-add shortcuts, category/payment method selection, date picker with future-date prevention
- **Edit & Delete** — Full CRUD with server-side validation on every field
- **View All Transactions** — Searchable, filterable, sortable table with pagination
- **Multi-filter System** — Filter by category, month, payment method, date range, and amount range simultaneously
- **Savings Tips** — Random financial tip displayed on the Transactions page

### Budgeting
- **Monthly Budgets** — Set a specific budget for any month/year combination
- **Recurring Budgets** — Auto-apply the same budget to all future months
- **Budget Progress Bar** — Visual progress indicator on Dashboard and Add Expense pages
- **Smart Alerts** — Dismissible banners: amber at 90%+ usage, red at 100%+ (persisted per session via localStorage)

### Analytics & Reporting
- **9-Section Analytics Dashboard** — Month selector, MoM comparison, category breakdown, daily spending bar chart, calendar heatmap, top 5 expenses, budget history, payment method breakdown, spending trend
- **Dashboard Overview** — 4 stat cards (Total Spent, This Month, Daily Average, Top Category), category donut chart, 6-month spending trend line chart
- **PDF Export** — Professional ReportLab-generated PDF with indigo header, summary stats, category breakdown table, full paginated expense list, and page numbers
- **CSV Export** — Client-side JavaScript CSV generation with one-click download

### User Management
- **Registration & Login** — Secure authentication with Werkzeug password hashing
- **Profile Editing** — Update username, email, and password with duplicate checks
- **Session Management** — Protected routes with login-required redirects

### Design & UX
- **Fintech Aesthetic** — Indigo color system, Inter font, glassmorphic cards, smooth transitions
- **Responsive Layout** — Full-width dashboard-style layouts on all pages
- **Active Navbar** — Current page highlighted with indigo bottom border
- **Auto-dismissing Flash Messages** — 4-second fade-out with smooth CSS animations
- **Custom Error Pages** — Branded 404 and 500 pages matching the app design
- **Animated Landing Page** — Floating stat cards with CSS keyframe animations

### Progressive Web App (PWA)
- **Installable** — Add to home screen on mobile and desktop
- **Service Worker** — Smart caching with cache-first for static assets, network-first for pages
- **Offline Support** — Branded offline fallback page when network is unavailable
- **App Icons** — Custom 192x192 and 512x512 indigo icons with stacked-layers logo

### Infrastructure
- **SQLAlchemy ORM** — Proper relational models with cascade deletes
- **Indexed Queries** — Database indexes on `user_id`, `date`, `username`, `email`, and composite `(user_id, date)`
- **Server-side Validation** — Regex-based input sanitization, whitelist validation for categories and payment methods, future-date blocking
- **Structured Logging** — All events logged to `expenseflow.log` with timestamps
- **Environment Variables** — `SECRET_KEY` loaded from `EXPENSEFLOW_SECRET_KEY` env var

---

## Screenshots

> Screenshots coming soon — the app is live at [m3hulraj.pythonanywhere.com](https://m3hulraj.pythonanywhere.com)

| Page | Description |
|------|-------------|
| Landing Page | Animated floating stat cards with fintech design |
| Dashboard | 4 stat cards, budget bar, category donut, trend chart |
| Transactions | Filterable table with search, export buttons, tip card |
| Analytics | 9-section deep-dive with calendar heatmap |
| Add Expense | Quick-add shortcuts, budget sidebar, full form |
| PDF Export | Professional indigo-themed expense report |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.x, Flask 3.1, Flask-SQLAlchemy |
| **Database** | SQLite via SQLAlchemy ORM |
| **Authentication** | Werkzeug security (pbkdf2 password hashing) |
| **Frontend** | HTML5, CSS3, JavaScript, Jinja2 templating |
| **UI Framework** | Bootstrap 5.3, Font Awesome 6.4 |
| **Charts** | Chart.js 4.4 |
| **Typography** | Google Fonts (Inter) |
| **PDF Generation** | ReportLab (Platypus layout engine) |
| **PWA** | Service Worker, Web App Manifest |
| **Date Handling** | python-dateutil (relativedelta) |
| **Deployment** | PythonAnywhere (WSGI) |

---

## What Makes This Different?

Most expense trackers are basic CRUD apps with minimal styling. ExpenseFlow is built to **production standards**:

- **Real fintech UI** — Not Bootstrap defaults. Custom design system with indigo palette, glassmorphic cards, micro-animations, and responsive layouts that look like a real SaaS product.
- **Smart budgeting** — Not just "set a number". Recurring budgets, visual progress bars, contextual warnings at 90% and 100% thresholds, and budget sidebar visible while adding expenses.
- **Deep analytics** — 9 analytical sections including calendar heatmaps, month-over-month comparisons, and payment method breakdowns. Not just "total spent this month".
- **PDF reports** — Professional, paginated PDF exports with styled tables, category breakdowns, and branded headers. Not a plain text dump.
- **PWA installable** — Service worker with intelligent caching strategies. Works offline. Installable on any device.
- **Production security** — Server-side validation on every input, future-date blocking, category whitelists, duplicate email checks, environment-variable secrets, and comprehensive error handling.

---

<h2 id="setup">Local Setup</h2>

### Prerequisites
- Python 3.10+ installed

### Installation

```bash
# Clone the repository
git clone https://github.com/M3hul-raj/ExpenseFlow.git
cd ExpenseFlow

# Create and activate virtual environment
python -m venv venv

# Windows
.\venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

Open your browser and navigate to **http://127.0.0.1:5000/**

### Environment Variables (Optional)

| Variable | Purpose | Default |
|----------|---------|---------|
| `EXPENSEFLOW_SECRET_KEY` | Flask session secret key | Dev fallback (change in production) |

---

## Deployment (PythonAnywhere)

1. Create a free account at [PythonAnywhere](https://www.pythonanywhere.com/)
2. Open a **Bash Console** and clone the repo:
   ```bash
   git clone https://github.com/M3hul-raj/ExpenseFlow.git
   cd ExpenseFlow
   ```
3. Create a virtual environment:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 myvenv
   pip install -r requirements.txt
   ```
4. Go to **Web** tab → **Add a new web app** → **Manual configuration** → Python 3.10
5. Set **Source code** to `/home/YOUR_USERNAME/ExpenseFlow`
6. Set **Virtualenv** to `myvenv`
7. Edit the **WSGI configuration file**:
   ```python
   import sys, os
   path = '/home/YOUR_USERNAME/ExpenseFlow'
   if path not in sys.path:
       sys.path.append(path)
   os.chdir(path)
   from app import app as application
   ```
8. Click **Reload** — your app is live!

---

## Project Structure

```
ExpenseFlow/
├── app.py                      # Flask application (all routes)
├── models.py                   # SQLAlchemy models (User, Expense, Budget)
├── requirements.txt            # Python dependencies
├── static/
│   ├── main.css                # Design system (fintech theme)
│   ├── sw.js                   # Service worker (PWA caching)
│   ├── manifest.json           # PWA web app manifest
│   └── icons/
│       ├── icon-192x192.png    # PWA icon (small)
│       └── icon-512x512.png    # PWA icon (large)
├── templates/
│   ├── base.html               # Base layout (navbar, flash, PWA)
│   ├── index.html              # Landing page
│   ├── login.html              # Sign in
│   ├── register.html           # Create account
│   ├── dashboard.html          # Main dashboard
│   ├── analytics.html          # 9-section analytics
│   ├── view_expense_updated.html  # Transactions list
│   ├── add_expense_updated.html   # Add expense form
│   ├── edit_expense.html       # Edit expense form
│   ├── set_budget.html         # Budget configuration
│   ├── edit_profile.html       # Profile management
│   ├── offline.html            # PWA offline fallback
│   ├── 404.html                # Custom 404 page
│   └── 500.html                # Custom 500 page
└── instance/
    └── expenses.db             # SQLite database (auto-created)
```

---

## License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">
  Built with Flask · Designed with care · <a href="https://m3hulraj.pythonanywhere.com">Try it live</a>
</p>
