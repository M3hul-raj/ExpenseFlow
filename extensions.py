"""
extensions.py — bare Flask extension objects.

Instantiated here (without an app) so that blueprints can import them
without circular imports.  Each extension is wired to the app inside
create_app() via init_app().
"""
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ── CSRF protection (Flask-WTF) ─────────────────────────────────────────────
# Automatically validates the csrf_token hidden field on every
# POST/PUT/PATCH/DELETE.  Wired to the app in create_app().
csrf = CSRFProtect()

# ── Rate limiting (Flask-Limiter) ────────────────────────────────────────────
# Keyed by the real client IP.  No default limit; limits are applied
# per-route.  Wired to the app in create_app().
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],       # no blanket limit — only /login is restricted
    storage_uri='memory://', # in-process store (swap for Redis in prod)
)
