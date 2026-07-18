# ExpenseFlow: Developer & Architecture Guide

Welcome to the internal documentation for **ExpenseFlow**. This guide is designed for developers, engineering managers, and technical recruiters to understand the underlying architecture, data flow, and design decisions of the application. 

If you are a developer looking to contribute or understand the codebase, this document serves as your complete "under the hood" manual.

---

## 1. Executive Architecture Summary

ExpenseFlow is a production-grade, full-stack web application built on a modern Python backend (Flask) with a custom, highly interactive vanilla JavaScript/CSS frontend. It uses the **application factory pattern** (`create_app()`) with **Flask Blueprints** and strictly implements the **MVC (Model-View-Controller)** pattern through server-side rendering (SSR):

*   **Model (`models.py`)**: Defines the SQLite database structure using SQLAlchemy ORM.
*   **View (`templates/`, `static/`)**: Jinja2 HTML templates styled with a completely custom CSS design system (`main.css`), featuring dynamic JavaScript interactivity without heavy frontend frameworks.
*   **Controller (`app.py` + `blueprints/`)**: The application factory in `app.py` wires extensions and registers 5 blueprints (`auth`, `expenses`, `budget`, `analytics`, `main`) that contain all route logic. Shared utilities live in `utils.py`, and extension instances (CSRF, rate limiter) are defined in `extensions.py` to avoid circular imports.

---

## 2. Complete File Directory Index

```text
ExpenseFlow/
├── .github/workflows/
│   └── ci.yml                  # GitHub Actions CI: pytest on every push/PR to main.
├── app.py                      # Application factory (create_app): config, extensions, blueprints.
├── extensions.py               # Bare Flask extension instances (CSRFProtect, Limiter).
├── models.py                   # SQLAlchemy database structure (User, Expense, Budget tables).
├── utils.py                    # Shared helpers: is_logged_in, get_user_budget, budget history, TIPS.
├── requirements.txt            # Python dependencies graph.
├── DEVELOPER_GUIDE.md          # This documentation file.
├── blueprints/
│   ├── __init__.py             # Package marker.
│   ├── auth.py                 # Auth routes: login, register, logout, dashboard, edit_profile.
│   ├── expenses.py             # Expense CRUD: add, view, edit, delete.
│   ├── budget.py               # Budget management: set_budget, adjust_budget, quick_adjust.
│   ├── analytics.py            # Analytics dashboard (9 sections) and PDF export.
│   └── main.py                 # PWA routes: /sw.js, /manifest.json, /offline.
├── tests/
│   ├── conftest.py             # Shared pytest fixtures (isolated in-memory SQLite per test).
│   └── test_app.py             # 26 functional tests: CRUD, budget logic, validation, CSRF.
├── static/
│   ├── main.css                # The core CSS Design System (CSS Variables, Dark/Light modes).
│   ├── avatars.css             # Avatar styling for profile selection.
│   ├── sw.js                   # Service Worker script handling PWA offline caching.
│   ├── manifest.json           # Web App Manifest for PWA installation.
│   └── icons/                  # Application icons.
├── templates/
│   ├── base.html               # The master Jinja2 wrapper (Navbar, Theme Toggle, Flash messages).
│   ├── index.html              # Animated landing page.
│   ├── login.html / register.html # Authentication views.
│   ├── dashboard.html          # Main overview (Stat cards, donut chart, trend lines).
│   ├── analytics.html          # Complex 9-section analytics (Heatmap, MoM trends).
│   ├── view_expense.html       # Transactions list with multi-parameter filtering.
│   ├── add_expense.html        # Form to add a new expense with server-side validation.
│   ├── set_budget.html         # Form to configure monthly or recurring budgets.
│   ├── edit_profile.html       # Account management page.
│   ├── 404.html / 500.html     # Custom error pages.
│   └── offline.html            # PWA offline fallback.
└── instance/
    └── expenses.db             # The SQLite database file (auto-generated).
```

---

## 3. Database Schema & Indexing

The application relies on three distinct relational tables mapped by SQLAlchemy, heavily optimized for read-heavy financial filtering.

1.  **User (`id`, `username`, `email`, `password_hash`, `date_created`)**
    *   The parent table utilizing Werkzeug `pbkdf2:sha256` password hashing.
2.  **Expense (`id`, `amount`, `category`, `description`, `date`, `payment_method`, `user_id`)**
    *   Linked to `User` via foreign key `user_id`.
    *   **Optimization:** Utilizes a **composite index** on `(user_id, date)` ensuring that complex month-over-month queries execute in $O(\log n)$ time.
    *   Categories and payment methods are validated server-side against strict whitelists.
3.  **Budget (`id`, `user_id`, `month`, `year`, `budget`, `is_recurring`)**
    *   Linked to a `User`.
    *   If `is_recurring` is True, the backend dynamically applies this budget to future months during runtime analytics generation.

> [!WARNING]
> **Cascade Deletes** are enforced at the ORM level. Deleting a User will automatically trigger the deletion of all their associated Expenses and Budgets to maintain referential integrity.

---

## 4. Key Technical Implementations (The "Magic")

### A. Flawless Dark/Light Mode via CSS Variables
Instead of relying on utility-first frameworks (like Tailwind) which clutter HTML, ExpenseFlow uses a highly scalable CSS Variable Architecture.
*   The `:root` pseudo-class defines the default Light Mode design tokens (e.g., `--bg-color: #F8FAFC`).
*   The `[data-theme="dark"]` attribute overrides these exact variables with dark variants.
*   This structural isolation prevents "mode contamination" and allows smooth `transition` animations across the entire application simultaneously.

### B. Algorithmic "GitHub-Style" Calendar Heatmap
Generating the 7-column calendar heatmap is done entirely from scratch without heavy charting libraries:
*   **Backend (`app.py`):** The python controller finds the user's maximum spending day for the selected month. It then calculates an `intensity` ratio (0.0 to 1.0) for every other day relative to that maximum.
*   **Frontend (`analytics.html`):** CSS Grid structures the days, and the Jinja2 template dynamically injects the calculated intensity into the `opacity` style attribute of each cell, creating a visually accurate, data-driven heatmap.

### C. Dynamic PDF Document Generation
The `/export/pdf` route utilizes the **ReportLab (`Platypus` engine)** to generate professional financial reports.
*   The PDF is generated dynamically in server memory using `io.BytesIO()`, ensuring zero disk-space bloat on the server.
*   It features custom table styling, pagination, and dynamic headers based on the current user's session data.

### D. Progressive Web App (PWA) Offline Resilience
The application utilizes a custom Service Worker (`sw.js`) to intercept network requests:
*   **Cache-First Strategy:** Static assets (CSS, logos, JS) are served instantly from the local cache.
*   **Network-First Strategy:** HTML pages attempt to fetch fresh data from the server, but gracefully fall back to a custom `offline.html` page if the user loses connectivity.

### E. High-Fidelity Glassmorphism & Animations
The landing page implements high-end visual design techniques seen in top-tier SaaS platforms.
*   **Glow Orb & Frosted Glass:** A heavily blurred, absolutely positioned `.hero-glow-orb` div sits behind the cards. The cards utilize `backdrop-filter: blur(24px)` to allow the gradient to organically bleed through the UI.
*   **Staggered Entrance Velocity:** Cards trigger a `slideUpFadeIn` entrance animation on load with staggered delays (`--enter-delay`), before gracefully transitioning into an infinite, multi-layered CSS keyframe float.

### F. True Velocity "Burn Rate" Analytics
Instead of simply dividing total monthly spend by 30 days, the Dashboard dynamically computes the user's "True Velocity".
*   It calculates the exact number of days that have passed in the current month to date (`max(1, datetime.now().day)`).
*   Dividing current spending by this exact integer gives an aggressive, highly accurate daily burn rate that forces real-time financial accountability.

### G. CSRF Protection & Login Rate Limiting
All POST forms include a hidden `csrf_token()` field validated by **Flask-WTF's CSRFProtect**. Extension instances are defined in `extensions.py` (not in `app.py`) to avoid circular imports with blueprints.
*   **Rate Limiting:** Flask-Limiter enforces **5 POST requests per 15 minutes** on `/login`. The `on_breach` callback returns a proper `make_response(render_template('login.html'), 429)` — not a raw string — so the styled login page renders correctly on the 429 response.
*   **Testing:** CSRF is disabled in the test configuration (`WTF_CSRF_ENABLED=False`) so functional tests can POST without tokens. Two dedicated tests re-enable CSRF to verify rejection without a valid token.

### H. Automated Testing & CI
The `tests/` directory contains **26 pytest tests** covering:
*   **Expense CRUD** — add, edit, delete with server-side validation (negative amounts, future dates, invalid categories)
*   **Cross-user isolation** — one user cannot edit/delete another user's expenses (returns 404)
*   **Budget logic** — default budget, explicit budget row, recurring fallback, override priority
*   **CSRF enforcement** — POST without token returns 400

Tests run against an isolated **in-memory SQLite database** created via `create_app('testing')` — the production `expenses.db` is never touched. **GitHub Actions CI** (`.github/workflows/ci.yml`) runs `pytest tests/ -v` on every push and pull request to `main`.

---

## 5. Deployment & Local Setup

### Local Development Setup
1. Clone the repository: `git clone https://github.com/M3hul-raj/ExpenseFlow.git`
2. Create and activate a virtual environment: `python -m venv venv`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the Flask development server: `python app.py`

### Production Deployment (WSGI)
When pushing updates to a live server (e.g., PythonAnywhere), the WSGI daemon must be reloaded after fetching the latest code.
```bash
git pull origin main
touch /var/www/your_username_pythonanywhere_com_wsgi.py
```

---

## 6. Portfolio & Resume Quick-Reference

For technical recruiters reviewing this repository, here is a summary of the engineering skills demonstrated in this codebase:

*   **Full Stack Architecture:** Engineered a modular MVC backend with Flask's application factory pattern and 5 Blueprints, using SQLAlchemy ORM with composite database indexing for high-performance query times.
*   **Security Hardening:** Implemented CSRF token validation on all POST forms via Flask-WTF, and brute-force login protection via Flask-Limiter (5 req / 15 min rate limit with custom 429 response rendering).
*   **Advanced Data Processing:** Developed complex data aggregation algorithms to feed a real-time 9-section analytics engine, calculating dynamic budget thresholds, MoM variances, and heatmap intensities.
*   **Testing & CI/CD:** Built a 26-test pytest suite with isolated in-memory database fixtures, integrated into a GitHub Actions CI pipeline running on every push and PR.
*   **UI/UX Engineering:** Designed a premium, glassmorphic UI with a scalable CSS variable architecture, implementing flawless, OS-aware Dark and Light modes.
*   **Web APIs & PWA:** Programmed a custom Service Worker with distinct "network-first" and "cache-first" caching strategies for offline resilience and mobile installation.
*   **Document Generation:** Built a custom pipeline using ReportLab to dynamically render and serve formatted, paginated PDF financial reports from memory.

---
*Built by Mehul Raj*
