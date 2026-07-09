"""
blueprints/main.py — PWA / static-asset routes.

The service worker must be served from the root scope (/sw.js) for full
PWA coverage, so these routes live here rather than in static/.
"""
from flask import Blueprint, send_from_directory, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/sw.js')
def service_worker():
    """Serve the service worker from root scope for full PWA coverage."""
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')


@main_bp.route('/manifest.json')
def manifest():
    """Serve the PWA web app manifest."""
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')


@main_bp.route('/offline')
def offline():
    """Offline fallback page shown by the service worker when network is unavailable."""
    return render_template('offline.html')
