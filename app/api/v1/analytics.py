"""Analytics API endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

from app.services.analytics_service import AnalyticsService
from app.models import User


bp = Blueprint('analytics', __name__)
logger = logging.getLogger(__name__)
analytics = AnalyticsService()


@bp.route('/dashboard', methods=['GET'])
@jwt_required()
def dashboard():
    """
    Get user dashboard analytics.
    
    Returns:
        Dashboard data with various metrics
    """
    try:
        user_id = get_jwt_identity()
        days = request.args.get('days', 30, type=int)
        
        # Get user activity summary
        activity_summary = analytics.get_user_activity_summary(user_id, days=days)
        
        return jsonify({
            'activity_summary': activity_summary,
            'period_days': days
        }), 200
        
    except Exception as e:
        logger.error(f"Dashboard analytics failed: {str(e)}")
        return jsonify({'error': 'Failed to get analytics'}), 500


@bp.route('/search-stats', methods=['GET'])
@jwt_required()
def search_stats():
    """Get search statistics."""
    try:
        days = request.args.get('days', 30, type=int)
        stats = analytics.get_search_analytics(days=days)
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Search stats failed: {str(e)}")
        return jsonify({'error': 'Failed to get search stats'}), 500


@bp.route('/popular-queries', methods=['GET'])
@jwt_required()
def popular_queries():
    """Get popular search queries."""
    try:
        days = request.args.get('days', 7, type=int)
        limit = min(request.args.get('limit', 10, type=int), 50)
        
        queries = analytics.get_popular_queries(days=days, limit=limit)
        
        return jsonify({
            'popular_queries': queries,
            'period_days': days
        }), 200
        
    except Exception as e:
        logger.error(f"Popular queries failed: {str(e)}")
        return jsonify({'error': 'Failed to get popular queries'}), 500
