"""
conftest.py — shared pytest fixtures for ExpenseFlow.

Isolation guarantee
───────────────────
Flask-SQLAlchemy caches the SQLAlchemy engine in
app.extensions['sqlalchemy']._engines (keyed by bind key).  Simply changing
SQLALCHEMY_DATABASE_URI is not enough — the old engine keeps pointing at
expenses.db.  And calling db.init_app() a second time is blocked by Flask 3.x
after the first request is handled (it tries to re-register teardown hooks).

Fix: store the initial extension state, then per-test swap its internal
_engines dict to force a fresh SQLAlchemy engine built from the test URI.
This never touches Flask's internal hook registry.
"""
import pytest
import sqlalchemy as sa

from app import app as flask_app, db, limiter
from models import User, Expense, Budget

# ─── Snapshot the real URI and the extension state created at import time ───
_REAL_URI = flask_app.config['SQLALCHEMY_DATABASE_URI']


def _swap_engine(uri: str) -> None:
    """
    Flush any live connections and replace the cached engine inside
    Flask-SQLAlchemy's extension state with a new one built from `uri`.

    Flask-SQLAlchemy stores per-app engines in:
        db._app_engines  →  WeakKeyDictionary{ app: {bind_key: engine} }

    We clear the inner dict and then rebuild the engine for the key `None`
    (the default engine) using `db._make_engine()`. This avoids calling
    db.init_app() again — which Flask 3.x blocks after the first request
    because it tries to re-register teardown hooks.
    """
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = uri
    per_app_engines = db._app_engines.setdefault(flask_app, {})
    for engine in list(per_app_engines.values()):
        engine.dispose()
    per_app_engines.clear()

    # Re-create and cache the new engine for the default bind (None)
    new_engine = db._make_engine(None, {"url": uri}, flask_app)
    per_app_engines[None] = new_engine



# ─── Core fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def app():
    """
    Fresh Flask app pointing at an isolated in-memory SQLite database.
    Tables are created before the test and dropped after it; the real
    expenses.db is never touched.
    """
    _swap_engine('sqlite:///:memory:')
    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'WTF_CSRF_CHECK_DEFAULT': False,
        'RATELIMIT_ENABLED': False,
    })

    # Save current limiter state and disable it for testing
    orig_limiter_enabled = limiter.enabled
    limiter.enabled = False

    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()

    # Restore rate limiter state
    limiter.enabled = orig_limiter_enabled

    # Restore the real database engine for any code that runs after tests.
    _swap_engine(_REAL_URI)


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
