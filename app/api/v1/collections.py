"""Collections API endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

from app.models import Collection, SearchResult
from app.services.analytics_service import AnalyticsService


bp = Blueprint('collections', __name__)
logger = logging.getLogger(__name__)
analytics = AnalyticsService()


@bp.route('/', methods=['GET', 'POST'])
@jwt_required()
def collections():
    """Handle collections list and creation."""
    if request.method == 'POST':
        return create_collection()
    else:
        return get_collections()


def create_collection():
    """Create a new collection."""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json() or {}
        
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        
        collection = Collection(
            user_id=user_id,
            project_id=data.get('project_id'),
            title=title,
            description=data.get('description', ''),
            is_public=data.get('is_public', False)
        )
        collection.save()
        
        analytics.track_activity(
            user_id=user_id,
            activity_type='collection_created',
            resource_type='collection',
            resource_id=collection.id
        )
        
        return jsonify({
            'message': 'Collection created',
            'collection': collection.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Create collection failed: {str(e)}")
        return jsonify({'error': 'Failed to create collection'}), 500


def get_collections():
    """Get user's collections."""
    try:
        user_id = int(get_jwt_identity())

        collections = Collection.query.filter_by(user_id=user_id).order_by(
            Collection.created_at.desc()
        ).all()

        return jsonify({
            'collections': [c.to_dict() for c in collections]
        }), 200

    except Exception as e:
        logger.error(f"Get collections failed: {str(e)}")
        return jsonify({'error': 'Failed to get collections'}), 500


@bp.route('/<int:collection_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
def collection_detail(collection_id):
    """Handle single collection operations."""
    if request.method == 'GET':
        return get_collection(collection_id)
    elif request.method == 'PUT':
        return update_collection(collection_id)
    else:
        return delete_collection(collection_id)


def get_collection(collection_id):
    """Get collection details with results."""
    try:
        user_id = int(get_jwt_identity())

        collection = Collection.query.filter_by(
            id=collection_id,
            user_id=user_id
        ).first()

        if not collection:
            return jsonify({'error': 'Collection not found'}), 404

        results = [r.to_dict() for r in collection.results]

        return jsonify({
            'collection': collection.to_dict(include_results=False),
            'results': results
        }), 200

    except Exception as e:
        logger.error(f"Get collection failed: {str(e)}")
        return jsonify({'error': 'Failed to get collection'}), 500


def update_collection(collection_id):
    """Update collection."""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json() or {}
        
        collection = Collection.query.filter_by(
            id=collection_id,
            user_id=user_id
        ).first()
        
        if not collection:
            return jsonify({'error': 'Collection not found'}), 404
        
        if 'title' in data:
            collection.title = data['title']
        if 'description' in data:
            collection.description = data['description']
        if 'is_public' in data:
            collection.is_public = data['is_public']
        
        collection.save()
        
        return jsonify({
            'message': 'Collection updated',
            'collection': collection.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Update collection failed: {str(e)}")
        return jsonify({'error': 'Failed to update collection'}), 500


def delete_collection(collection_id):
    """Delete collection."""
    try:
        user_id = int(get_jwt_identity())

        collection = Collection.query.filter_by(
            id=collection_id,
            user_id=user_id
        ).first()

        if not collection:
            return jsonify({'error': 'Collection not found'}), 404

        collection.delete()

        return jsonify({'message': 'Collection deleted', 'collection_id': collection_id}), 200

    except Exception as e:
        logger.error(f"Delete collection failed: {str(e)}")
        return jsonify({'error': 'Failed to delete collection'}), 500


@bp.route('/<int:collection_id>/results/<int:result_id>', methods=['POST', 'DELETE'])
@jwt_required()
def manage_collection_result(collection_id, result_id):
    """Add or remove result from collection."""
    try:
        user_id = int(get_jwt_identity())

        collection = Collection.query.filter_by(
            id=collection_id,
            user_id=user_id
        ).first()

        if not collection:
            return jsonify({'error': 'Collection not found'}), 404

        result = SearchResult.get_by_id(result_id)
        if not result:
            return jsonify({'error': 'Result not found'}), 404

        if request.method == 'POST':
            if result not in collection.results:
                collection.results.append(result)
                collection.save()
            return jsonify({
                'message': 'Result added to collection',
                'collection': collection.to_dict()
            }), 200
        else:
            if result in collection.results:
                collection.results.remove(result)
                collection.save()
            return jsonify({
                'message': 'Result removed from collection',
                'collection': collection.to_dict()
            }), 200

    except Exception as e:
        logger.error(f"Manage collection result failed: {str(e)}")
        return jsonify({'error': 'Operation failed'}), 500
