# ExpenseFlow: Developer & Architecture Guide

Welcome to the internal documentation for **ExpenseFlow**. This guide is designed for developers, engineering managers, and technical recruiters to understand the underlying architecture, data flow, and design decisions of the application. 

If you are a developer looking to contribute or understand the codebase, this document serves as your complete "under the hood" manual.

---

## 1. Executive Architecture Summary

ExpenseFlow is a production-grade, full-stack web application built on a modern Python backend (Flask) with a custom, highly interactive vanilla JavaScript/CSS frontend. It strictly implements the **MVC (Model-View-Controller)** pattern through server-side rendering (SSR):

*   **Model (`models.py`)**: Defines the SQLite database structure using SQLAlchemy ORM.
*   **View (`templates/`, `static/`)**: Jinja2 HTML templates styled with a completely custom CSS design system (`main.css`), featuring dynamic JavaScript interactivity without heavy frontend frameworks.
*   **Controller (`app.py`)**: The central Flask application handling routing, business logic, authentication, PDF generation, and complex analytics processing.

---

## 2. Complete File Directory Index

```text
ExpenseFlow/
├── app.py                      # Central controller: routes, auth, PDF generation, analytics math.
├── models.py                   # SQLAlchemy database structure (User, Expense, Budget tables).
├── requirements.txt            # Python dependencies graph.
├── DEVELOPER_GUIDE.md          # This documentation file.
├── static/
│   ├── main.css                # The core CSS Design System (CSS Variables, Dark/Light modes).
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
│   └── edit_profile.html       # Account management page.
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

*   **Full Stack Architecture:** Engineered a custom MVC backend with Flask and SQLAlchemy ORM, utilizing composite database indexing to achieve high-performance query times.
*   **Advanced Data Processing:** Developed complex data aggregation algorithms to feed a real-time 9-section analytics engine, calculating dynamic budget thresholds, MoM variances, and heatmap intensities.
*   **UI/UX Engineering:** Designed a premium, glassmorphic UI with a scalable CSS variable architecture, implementing flawless, OS-aware Dark and Light modes.
*   **Web APIs & PWA:** Programmed a custom Service Worker with distinct "network-first" and "cache-first" caching strategies for offline resilience and mobile installation.
*   **Document Generation:** Built a custom pipeline using ReportLab to dynamically render and serve formatted, paginated PDF financial reports from memory.

---
*Built by Mehul Raj*
