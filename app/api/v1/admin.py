"""Admin API endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

from app.models import User
from app.services.analytics_service import AnalyticsService
from app.utils.exceptions import AuthorizationError


bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)
analytics = AnalyticsService()


def require_admin(func):
    """Decorator to require admin role."""
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.get_by_id(user_id)
        
        if not user or user.role.value != 'admin':
            raise AuthorizationError("Admin access required")
        
        return func(*args, **kwargs)
    
    wrapper.__name__ = func.__name__
    return wrapper


@bp.route('/users', methods=['GET'])
@jwt_required()
@require_admin
def get_users():
    """Get all users (admin only)."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        pagination = User.query.order_by(User.created_at.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        return jsonify({
            'users': [u.to_dict() for u in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages
        }), 200
        
    except AuthorizationError as e:
        return jsonify({'error': str(e)}), 403
    except Exception as e:
        logger.error(f"Get users failed: {str(e)}")
        return jsonify({'error': 'Failed to get users'}), 500


@bp.route('/stats', methods=['GET'])
@jwt_required()
@require_admin
def system_stats():
    """Get system-wide statistics (admin only)."""
    try:
        days = request.args.get('days', 30, type=int)
        
        # Get various stats
        search_stats = analytics.get_search_analytics(days=days)
        user_growth = analytics.get_user_growth(days=days)
        popular_queries = analytics.get_popular_queries(days=days, limit=10)
        
        return jsonify({
            'search_stats': search_stats,
            'user_growth': user_growth,
            'popular_queries': popular_queries,
            'period_days': days
        }), 200
        
    except AuthorizationError as e:
        return jsonify({'error': str(e)}), 403
    except Exception as e:
        logger.error(f"System stats failed: {str(e)}")
        return jsonify({'error': 'Failed to get stats'}), 500
