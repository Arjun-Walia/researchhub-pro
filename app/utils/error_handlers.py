"""Error handlers for the application."""
from flask import jsonify, request, render_template
from werkzeug.exceptions import HTTPException

from app.utils.exceptions import (
    ResearchHubException,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    RateLimitError,
    ExternalAPIError
)


def register_handlers(app):
    """Register error handlers with the Flask app."""
    def handle_error(status_code, message, title=None):
        """Return JSON for API routes or render HTML error page for web routes."""
        if request.path.startswith('/api/') or request.accept_mimetypes.best == 'application/json':
            return jsonify({'error': message}), status_code

        context = {
            'status_code': status_code,
            'title': title or 'Something went wrong',
            'message': message,
        }
        return render_template('error.html', **context), status_code
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        return handle_error(400, str(e), 'Validation error')
    
    @app.errorhandler(AuthenticationError)
    def handle_authentication_error(e):
        return handle_error(401, str(e), 'Authentication required')
    
    @app.errorhandler(AuthorizationError)
    def handle_authorization_error(e):
        return handle_error(403, str(e), 'Access denied')
    
    @app.errorhandler(ResourceNotFoundError)
    def handle_not_found_error(e):
        return handle_error(404, str(e), 'Not found')
    
    @app.errorhandler(RateLimitError)
    def handle_rate_limit_error(e):
        return handle_error(429, str(e), 'Too many requests')
    
    @app.errorhandler(ExternalAPIError)
    def handle_external_api_error(e):
        return handle_error(502, str(e), 'Upstream service error')
    
    @app.errorhandler(ResearchHubException)
    def handle_base_exception(e):
        return handle_error(500, str(e), 'Application error')
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        return handle_error(e.code, e.description, 'Request error')
    
    @app.errorhandler(404)
    def handle_404(e):
        return handle_error(404, 'We could not find the page you requested.', 'Page not found')
    
    @app.errorhandler(500)
    def handle_500(e):
        app.logger.error(f"Internal server error: {str(e)}")
        return handle_error(500, 'An unexpected error occurred. Please try again later.', 'Internal server error')
