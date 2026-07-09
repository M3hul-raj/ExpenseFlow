import logging
import os
from flask import Flask, render_template
from models import db
from extensions import csrf, limiter

# ── Logging setup ─────────────────────────────────────────────────────────────
# Logs to a rotating file in the project root; INFO level for general events,
# WARNING/ERROR for security/DB issues.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('expenseflow.log', encoding='utf-8'),
        logging.StreamHandler(),         # also print to console in dev
    ]
)
logger = logging.getLogger('expenseflow')


def create_app(config_name='production'):
    """
    Application factory.

    config_name='production'  →  SQLite file DB, CSRF + rate-limit active.
    config_name='testing'     →  in-memory SQLite, CSRF + rate-limit disabled.

    The module-level  app = create_app()  below preserves compatibility with
    gunicorn and  python app.py  — nothing in deployment needs to change.
    """
    app = Flask(__name__)

    # ── Jinja filters ─────────────────────────────────────────────────────
    @app.template_filter('currency')
    def format_currency(value):
        """Formats a float/int into Indian Rupee format."""
        try:
            value = float(value)
            return f"₹{value:,.2f}"
        except (ValueError, TypeError):
            return "₹0.00"

    # ── Config ────────────────────────────────────────────────────────────
    # SECRET_KEY: read from environment in production; strong fallback for dev
    app.secret_key = os.environ.get('EXPENSEFLOW_SECRET_KEY', 'dev-only-fallback-change-in-prod-!@#')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # WTF_CSRF_TIME_LIMIT: how long (seconds) a CSRF token stays valid; None = session lifetime
    app.config['WTF_CSRF_TIME_LIMIT'] = None

    if config_name == 'testing':
        app.config.update({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'WTF_CSRF_ENABLED': False,
            'WTF_CSRF_CHECK_DEFAULT': False,
            'RATELIMIT_ENABLED': False,
        })
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'

    # ── Extensions ────────────────────────────────────────────────────────
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # ── Blueprints ────────────────────────────────────────────────────────
    from blueprints.main      import main_bp
    from blueprints.auth      import auth_bp
    from blueprints.expenses  import expenses_bp
    from blueprints.budget    import budget_bp
    from blueprints.analytics import analytics_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(analytics_bp)

    # ── Error handlers ────────────────────────────────────────────────────
    @app.errorhandler(404)
    def page_not_found(e):
        """Render a branded 404 page for any missing route."""
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        """Render a branded 500 page for any unhandled server error."""
        db.session.rollback()  # safety: clear any broken transaction
        return render_template('500.html'), 500

    # ── Database ──────────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()

    return app


# ── Module-level app ──────────────────────────────────────────────────────────
# Preserved so that  gunicorn app:app  and  python app.py  continue to work
# without any deployment changes.
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
