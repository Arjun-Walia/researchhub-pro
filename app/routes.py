"""Web routes for the frontend."""
from flask import Blueprint, render_template, request, current_app

bp = Blueprint('web', __name__)


@bp.route('/')
def index():
    """Landing page."""
    return render_template('index.html')


@bp.route('/dashboard')
def dashboard():
    """Dashboard page."""
    return render_template('dashboard.html')


@bp.route('/search')
def search():
    """Search page."""
    return render_template('search.html')


@bp.route('/collections')
def collections():
    """Collections page."""
    return render_template('collections.html')


@bp.route('/projects')
def projects():
    """Projects page."""
    return render_template('projects.html')


@bp.route('/search-history')
def search_history():
    """Search history list page."""
    return render_template('search_history.html')


@bp.route('/search-history/<int:query_id>')
def search_history_detail(query_id):
    """Individual query detail page."""
    return render_template('query_detail.html', query_id=query_id)


@bp.route('/profile')
def profile():
    """User profile page."""
    return render_template('profile.html')


@bp.route('/settings')
def settings():
    """Account settings page."""
    return render_template('settings.html')


@bp.route('/login')
def login():
    """Login page."""
    return render_template('login.html')


@bp.route('/register')
def register():
    """Registration page with optional plan context."""
    return render_template('register.html', plan=request.args.get('plan'))


@bp.route('/forgot-password')
def forgot_password():
    """Password recovery request page."""
    return render_template('forgot_password.html')


@bp.route('/reset-password')
def reset_password():
    """Password reset confirmation page."""
    return render_template('reset_password.html', token=request.args.get('token'))


@bp.route('/logout')
def logout():
    """Logout helper page to clear tokens client-side."""
    return render_template('logout.html')


@bp.route('/privacy')
def privacy():
    """Privacy policy page."""
    return render_template('privacy.html')


@bp.route('/terms')
def terms():
    """Terms of use page."""
    return render_template('terms.html')


@bp.route('/health')
def health_check():
    """Health check endpoint."""
    return {'status': 'healthy', 'version': current_app.config['VERSION']}, 200
