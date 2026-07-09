"""
conftest.py — shared pytest fixtures for ExpenseFlow.

Isolation guarantee
───────────────────
Each test function gets a completely fresh Flask application instance created
via create_app('testing'), which uses:
  - sqlite:///:memory:   (never touches the real expenses.db)
  - WTF_CSRF_ENABLED=False
  - RATELIMIT_ENABLED=False

Tables are created fresh before each test and dropped after it.
The old _swap_engine private-attribute hack is gone entirely — it was only
needed because we were mutating the module-level app object.  The factory
gives each test its own isolated app with no shared state.
"""
import pytest
from app import create_app
from models import db, User, Expense, Budget


# ─── Core fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def app():
    """
    Fresh Flask app pointing at an isolated in-memory SQLite database.
    Tables are created before the test and dropped after it; the real
    expenses.db is never touched.
    """
    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


@pytest.fixture
def user(app):
    """A committed User (alice) for the duration of one test."""
    u = User(username='alice', email='alice@test.com')
    u.set_password('password123')
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def user2(app):
    """A second committed User (bob) — used for cross-user access tests."""
    u = User(username='bob', email='bob@test.com')
    u.set_password('password123')
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def auth_client(client, user):
    """
    Test client already logged in as alice.
    Depends on `user` so alice exists in the DB before the login POST.
    """
    client.post(
        '/login',
        data={'username': 'alice', 'password': 'password123'},
        follow_redirects=True,
    )
    return client
