# ExpenseFlow

ExpenseFlow is a lightweight, intuitive, and feature-rich personal finance tracker built with Python and Flask. It empowers users to take control of their financial health by tracking daily expenses, setting monthly/recurring budgets, and analyzing spending habits.

Unlike heavy database-driven applications, ExpenseFlow is designed to be highly portable, utilizing a robust text-file-based backend (`.txt`) for persistent data storage. This makes it incredibly easy to deploy, migrate, and run on any machine without needing a complex SQL database setup.

## Features
- **User Authentication:** Secure registration and login system with hashed passwords.
- **Expense Tracking:** Add, edit, and delete expenses categorized by custom types and payment methods.
- **Budgeting System:** Set specific monthly budgets or global recurring budgets with visual progress indicators.
- **Analytics Dashboard:** Visual breakdowns of spending trends, categorical insights, and monthly performance.
- **Portability:** Data is stored in individual text files, making data backups as easy as copying a folder.

---

## Tech Stack
- **Backend:** Python 3.x, Flask, Werkzeug (for security hashing)
- **Frontend:** HTML5, Vanilla CSS, Jinja2 Templating
- **Data Storage:** File-system based storage (Flat `.txt` files)

---

## How to Run it Locally

Follow these steps to run ExpenseFlow on your own machine.

### Prerequisites
- Python 3.x installed on your computer.

### Setup Instructions
1. **Clone the repository:**
   ```bash
   git clone https://github.com/M3hul-raj/ExpenseFlow.git
   cd ExpenseFlow
   ```
2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```
3. **Activate the virtual environment:**
   - **Windows:** `.\venv\Scripts\activate`
   - **Mac/Linux:** `source venv/bin/activate`
4. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
5. **Run the Application:**
   ```bash
   python app.py
   ```
6. **Access the App:** 
   Open your browser and navigate to `http://127.0.0.1:5000/`

---

## Deployment Information

ExpenseFlow is specifically optimized to be deployed on **PythonAnywhere** for free, permanent hosting that natively supports persistent text-file storage.

### Deploying to PythonAnywhere
1. Create a free account at [PythonAnywhere](https://www.pythonanywhere.com/).
2. Open a **Bash Console** in PythonAnywhere and clone your GitHub repository:
   ```bash
   git clone https://github.com/M3hul-raj/ExpenseFlow.git
   cd ExpenseFlow
   ```
3. Create a virtual environment and install dependencies:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 myvenv
   pip install -r requirements.txt
   ```
4. Navigate to the **Web** tab and click **Add a new web app**.
5. Choose **Manual configuration** and select the same Python version used for your virtual environment.
6. In the **Virtualenv** section, type `myvenv`.
7. In the **Code** section:
   - Set the **Source code** path to `/home/YOUR_PYTHONANYWHERE_USERNAME/ExpenseFlow`
   - Click the **WSGI configuration file** link, delete its contents, and replace it with:
   ```python
   import sys
   import os

   path = '/home/YOUR_PYTHONANYWHERE_USERNAME/ExpenseFlow'
   if path not in sys.path:
       sys.path.append(path)

   # Move to project directory to enable relative text-file parsing
   os.chdir(path)

   from app import app as application
   ```
8. Save the WSGI file, return to the **Web** tab, and click the green **Reload** button. Your app is now live!
