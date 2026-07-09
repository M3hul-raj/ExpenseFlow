"""
test_app.py — ExpenseFlow test suite (pytest + Flask test client).

All tests run against an isolated in-memory SQLite database (see conftest.py).
CSRF and rate-limiting are disabled globally per test; one dedicated test
re-enables CSRF to prove rejection without a token.

Coverage areas
──────────────
1.  add_expense  — validation (negative / zero / invalid category) + persistence
2.  edit_expense — updates only the targeted row; wrong-user → 404
3.  delete_expense — GET → 405; POST removes only that row; wrong-user → 404
4.  Budget helpers — get_user_budget / get_budget_history against known I/O
5.  CSRF — POST without token → 400; POST with valid token → passes CSRF check
"""
import re

import pytest

from app import db, get_user_budget, get_budget_history, get_current_year_month
from models import User, Expense, Budget


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_expense(user_id: int, **overrides) -> Expense:
    """Insert and commit a minimal Expense row; return the ORM object."""
    defaults = dict(
        date='2026-07-09',
        category='Food',
        amount=100.0,
        description='Test expense',
        payment_method='Cash',
    )
    defaults.update(overrides)
    e = Expense(user_id=user_id, **defaults)
    db.session.add(e)
    db.session.commit()
    return e


# ══════════════════════════════════════════════════════════════════════════════
# 1. add_expense — validation
# ══════════════════════════════════════════════════════════════════════════════

class TestAddExpenseValidation:

    def test_negative_amount_rejected(self, auth_client):
        resp = auth_client.post('/add', data={
            'date': '2026-07-09', 'category': 'Food',
            'amount': '-50', 'description': 'x', 'payment_method': 'Cash',
        }, follow_redirects=True)
        assert b'valid positive amount' in resp.data

    def test_zero_amount_rejected(self, auth_client):
        resp = auth_client.post('/add', data={
            'date': '2026-07-09', 'category': 'Food',
            'amount': '0', 'description': 'x', 'payment_method': 'Cash',
        }, follow_redirects=True)
        assert b'valid positive amount' in resp.data

    def test_missing_category_rejected(self, auth_client):
        resp = auth_client.post('/add', data={
            'date': '2026-07-09', 'category': '',
            'amount': '100', 'description': 'x', 'payment_method': 'Cash',
        }, follow_redirects=True)
        assert b'valid category' in resp.data

    def test_invalid_category_rejected(self, auth_client):
        """A category not in the whitelist must be rejected."""
        resp = auth_client.post('/add', data={
            'date': '2026-07-09', 'category': 'Gambling',
            'amount': '100', 'description': 'x', 'payment_method': 'Cash',
        }, follow_redirects=True)
        assert b'valid category' in resp.data

    def test_future_date_rejected(self, auth_client):
        resp = auth_client.post('/add', data={
            'date': '2099-01-01', 'category': 'Food',
            'amount': '100', 'description': 'x', 'payment_method': 'Cash',
        }, follow_redirects=True)
        assert b'cannot be in the future' in resp.data

    def test_valid_input_persists_to_db(self, auth_client, user):
        auth_client.post('/add', data={
            'date': '2026-07-09', 'category': 'Food',
            'amount': '99.99', 'description': 'Lunch', 'payment_method': 'UPI',
        }, follow_redirects=True)
        # Expire session cache so we read fresh data from the DB
        db.session.expire_all()
        expense = Expense.query.filter_by(user_id=user.id).first()
        assert expense is not None
        assert expense.amount == 99.99
        assert expense.category == 'Food'
        assert expense.description == 'Lunch'
        assert expense.payment_method == 'UPI'


# ══════════════════════════════════════════════════════════════════════════════
# 2. edit_expense
# ══════════════════════════════════════════════════════════════════════════════

class TestEditExpense:

    def test_updates_only_targeted_row(self, auth_client, user):
        e1 = _make_expense(user.id, category='Food', amount=100.0)
        e2 = _make_expense(user.id, category='Transport', amount=50.0)

        auth_client.post(f'/edit/{e1.id}', data={
            'date': '2026-07-09', 'category': 'Health',
            'amount': '75.00', 'description': 'Updated', 'payment_method': 'Cash',
        }, follow_redirects=True)

        db.session.expire_all()
        updated  = db.session.get(Expense, e1.id)
        untouched = db.session.get(Expense, e2.id)

        assert updated.category == 'Health'
        assert updated.amount   == 75.0
        # e2 must be completely untouched
        assert untouched.category == 'Transport'
        assert untouched.amount   == 50.0

    def test_wrong_user_returns_404(self, client, user, user2):
        """bob must not be able to edit alice's expense."""
        e = _make_expense(user.id)

        # Log in as bob
        client.post('/login',
                    data={'username': 'bob', 'password': 'password123'},
                    follow_redirects=True)
        resp = client.get(f'/edit/{e.id}')
        assert resp.status_code == 404

        # The expense must still exist unchanged
        db.session.expire_all()
        assert db.session.get(Expense, e.id) is not None

    def test_nonexistent_id_returns_404(self, auth_client):
        resp = auth_client.get('/edit/999999')
        assert resp.status_code == 404

    def test_validation_rejects_invalid_data_on_edit(self, auth_client, user):
        """Editing with a bad category should flash an error, not save."""
        e = _make_expense(user.id, category='Food', amount=100.0)

        auth_client.post(f'/edit/{e.id}', data={
            'date': '2026-07-09', 'category': 'INVALID_CAT',
            'amount': '50', 'description': 'x', 'payment_method': 'Cash',
        }, follow_redirects=True)

        db.session.expire_all()
        assert db.session.get(Expense, e.id).category == 'Food'  # unchanged


# ══════════════════════════════════════════════════════════════════════════════
# 3. delete_expense
# ══════════════════════════════════════════════════════════════════════════════

class TestDeleteExpense:

    def test_get_request_returns_405(self, auth_client, user):
        e = _make_expense(user.id)
        resp = auth_client.get(f'/delete/{e.id}')
        assert resp.status_code == 405
        # GET must NOT have deleted the row
        db.session.expire_all()
        assert db.session.get(Expense, e.id) is not None

    def test_post_removes_only_targeted_row(self, auth_client, user):
        e1 = _make_expense(user.id, amount=100.0)
        e2 = _make_expense(user.id, amount=200.0)

        auth_client.post(f'/delete/{e1.id}', follow_redirects=True)

        db.session.expire_all()
        assert db.session.get(Expense, e1.id) is None      # deleted ✓
        assert db.session.get(Expense, e2.id) is not None  # untouched ✓

    def test_wrong_user_returns_404(self, client, user, user2):
        """bob POSTing to delete alice's expense must get 404 (not delete it)."""
        e = _make_expense(user.id)

        client.post('/login',
                    data={'username': 'bob', 'password': 'password123'},
                    follow_redirects=True)
        resp = client.post(f'/delete/{e.id}', follow_redirects=False)
        assert resp.status_code == 404

        db.session.expire_all()
        assert db.session.get(Expense, e.id) is not None  # still exists ✓

    def test_nonexistent_id_returns_404(self, auth_client):
        resp = auth_client.post('/delete/999999', follow_redirects=False)
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 4. Budget helper functions
# ══════════════════════════════════════════════════════════════════════════════

class TestBudgetFunctions:

    def test_get_user_budget_default(self, app, user):
        """No Budget row, no recurring_budget → default 2000."""
        assert get_user_budget(user.id, '2026-01') == 2000.0

    def test_get_user_budget_explicit_row(self, app, user):
        b = Budget(user_id=user.id, year_month='2026-07', amount=5000.0)
        db.session.add(b)
        db.session.commit()
        assert get_user_budget(user.id, '2026-07') == 5000.0

    def test_get_user_budget_recurring_fallback(self, app, user):
        """No explicit Budget for the month → fall back to user.recurring_budget."""
        u = db.session.get(User, user.id)
        u.recurring_budget = 3500.0
        db.session.commit()
        assert get_user_budget(user.id, '2099-12') == 3500.0

    def test_get_user_budget_explicit_overrides_recurring(self, app, user):
        """Explicit Budget row wins over recurring_budget."""
        u = db.session.get(User, user.id)
        u.recurring_budget = 3500.0
        db.session.commit()
        b = Budget(user_id=user.id, year_month='2026-07', amount=8000.0)
        db.session.add(b)
        db.session.commit()
        assert get_user_budget(user.id, '2026-07') == 8000.0

    def test_get_budget_history_returns_n_months(self, app, user):
        history = get_budget_history(user.id, months=6)
        assert len(history) == 6
        required_keys = {'month', 'year_month', 'budget', 'spending', 'status', 'remaining'}
        for item in history:
            assert required_keys <= item.keys(), \
                f"Missing keys {required_keys - item.keys()} in history item"

    def test_get_budget_history_status_on_track(self, app, user):
        ym = get_current_year_month()
        db.session.add(Budget(user_id=user.id, year_month=ym, amount=5000.0))
        db.session.commit()
        history = get_budget_history(user.id, months=1)
        assert history[0]['status'] == 'On Track'

    def test_get_budget_history_status_near_limit(self, app, user):
        ym = get_current_year_month()
        db.session.add(Budget(user_id=user.id, year_month=ym, amount=1000.0))
        db.session.add(Expense(user_id=user.id, date=ym + '-01', category='Food',
                               amount=950.0, description='x', payment_method='Cash'))
        db.session.commit()
        history = get_budget_history(user.id, months=1)
        assert history[0]['status'] == 'Near Limit'

    def test_get_budget_history_status_over_budget(self, app, user):
        ym = get_current_year_month()
        db.session.add(Budget(user_id=user.id, year_month=ym, amount=10.0))
        db.session.add(Expense(user_id=user.id, date=ym + '-01', category='Food',
                               amount=500.0, description='x', payment_method='Cash'))
        db.session.commit()
        history = get_budget_history(user.id, months=1)
        assert history[0]['status'] == 'Over Budget'

    def test_get_budget_history_remaining_calculation(self, app, user):
        ym = get_current_year_month()
        db.session.add(Budget(user_id=user.id, year_month=ym, amount=1000.0))
        db.session.add(Expense(user_id=user.id, date=ym + '-01', category='Food',
                               amount=300.0, description='x', payment_method='Cash'))
        db.session.commit()
        history = get_budget_history(user.id, months=1)
        assert history[0]['remaining'] == pytest.approx(700.0)


# ══════════════════════════════════════════════════════════════════════════════
# 5. CSRF
# ══════════════════════════════════════════════════════════════════════════════

class TestCSRF:

    def test_post_without_csrf_token_returns_400(self, app):
        """
        When CSRF is enabled, a POST that omits the csrf_token field must
        return 400 — not execute the route logic.
        """
        app.config['WTF_CSRF_ENABLED'] = True
        app.config['WTF_CSRF_CHECK_DEFAULT'] = True
        try:
            c = app.test_client()
            resp = c.post('/login',
                          data={'username': 'nobody', 'password': 'wrong'})
            assert resp.status_code == 400, (
                f"Expected 400 (CSRF rejected), got {resp.status_code}"
            )
        finally:
            # Always restore so the next test is not affected
            app.config['WTF_CSRF_ENABLED'] = False
            app.config['WTF_CSRF_CHECK_DEFAULT'] = False

    def test_post_with_valid_csrf_token_passes_csrf_check(self, app):
        """
        GET the login page (seeds the session token), then POST with that
        token.  CSRF validation must pass; the response must not be 400.
        Wrong credentials will flash an error, but that is route logic — not
        CSRF rejection.
        """
        app.config['WTF_CSRF_ENABLED'] = True
        app.config['WTF_CSRF_CHECK_DEFAULT'] = True
        try:
            c = app.test_client()

            # Step 1: GET seeds the session with a CSRF token
            get_resp = c.get('/login')
            assert get_resp.status_code == 200

            # Step 2: extract the token from the rendered hidden field
            html = get_resp.data.decode()
            match = re.search(
                r'name=["\']csrf_token["\'][^>]+value=["\']([^"\']+)["\']'
                r'|value=["\']([^"\']+)["\'][^>]+name=["\']csrf_token["\']',
                html,
            )
            assert match, "csrf_token hidden field not found in login page HTML"
            token = match.group(1) or match.group(2)

            # Step 3: POST with the valid token
            resp = c.post('/login', data={
                'username': 'nobody', 'password': 'wrong',
                'csrf_token': token,
            }, follow_redirects=True)

            # CSRF check passes → route logic runs → we get a flash/redirect,
            # NOT a 400 CSRF error.
            assert resp.status_code == 200

        finally:
            app.config['WTF_CSRF_ENABLED'] = False
            app.config['WTF_CSRF_CHECK_DEFAULT'] = False

    def test_delete_post_without_csrf_token_returns_400(self, app, user):
        """The delete route (POST-only) is also CSRF-protected."""
        e = _make_expense(user.id)
        app.config['WTF_CSRF_ENABLED'] = True
        app.config['WTF_CSRF_CHECK_DEFAULT'] = True
        try:
            c = app.test_client()
            # Log in without CSRF (briefly disable just for login, then re-enable)
            app.config['WTF_CSRF_ENABLED'] = False
            c.post('/login',
                   data={'username': 'alice', 'password': 'password123'},
                   follow_redirects=True)
            app.config['WTF_CSRF_ENABLED'] = True

            resp = c.post(f'/delete/{e.id}')
            assert resp.status_code == 400

            # Row must still exist — CSRF rejection prevented the delete
            db.session.expire_all()
            assert db.session.get(Expense, e.id) is not None
        finally:
            app.config['WTF_CSRF_ENABLED'] = False
            app.config['WTF_CSRF_CHECK_DEFAULT'] = False
