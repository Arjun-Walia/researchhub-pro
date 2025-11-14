"""Research API endpoints."""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

from sqlalchemy.orm import joinedload
from typing import Optional, Dict
from urllib.parse import quote_plus

from app.models import User, Query, SearchResult, ResearchProject
from app.models.research import QueryType
from app.services.exa_service import PerplexitySearchService
from app.services.ai_service import AIService
from app.services.serpapi_service import SerpAPISearchService
from app.services.search_router import (
    SearchOrchestrator,
    OpenAISearchProvider,
    PerplexitySearchProvider,
    SerpAPISearchProvider,
)
from app.services.analytics_service import AnalyticsService
from app.utils.exceptions import QuotaExceededError, ExternalAPIError, RateLimitError
from app import limiter


bp = Blueprint('research', __name__)
logger = logging.getLogger(__name__)
analytics = AnalyticsService()


def get_services(user: Optional[User] = None):
    """Get service instances for search and AI flows."""
    cache = getattr(current_app, 'cache', None)
    perplexity_key = None

    if user:
        try:
            perplexity_key = user.get_integration_key('perplexity')
        except AttributeError:
            perplexity_key = None

    if not perplexity_key and current_app.config.get('PERPLEXITY_API_KEY'):
        perplexity_key = current_app.config.get('PERPLEXITY_API_KEY')
    elif current_app.config.get('PERPLEXITY_SHARED_API_KEY'):
        perplexity_key = current_app.config.get('PERPLEXITY_SHARED_API_KEY')

    openai_key = None
    anthropic_key = None
    if user:
        try:
            openai_key = user.get_integration_key('openai')
            anthropic_key = user.get_integration_key('anthropic')
        except AttributeError:
            openai_key = openai_key or None
            anthropic_key = anthropic_key or None

    if not openai_key:
        openai_key = current_app.config.get('OPENAI_API_KEY')
    if not anthropic_key:
        anthropic_key = current_app.config.get('ANTHROPIC_API_KEY')

    search_service = PerplexitySearchService(
        api_key=perplexity_key,
        cache=cache,
        base_url=current_app.config.get('PERPLEXITY_API_BASE_URL'),
        default_model=current_app.config.get('PERPLEXITY_DEFAULT_MODEL'),
        timeout=current_app.config.get('SEARCH_TIMEOUT', 30)
    )
    ai = AIService(
        openai_key=openai_key,
        anthropic_key=anthropic_key,
        perplexity_key=perplexity_key,
        perplexity_base_url=current_app.config.get('PERPLEXITY_API_BASE_URL')
    )

    serpapi_key = None
    if user:
        try:
            serpapi_key = user.get_integration_key('serpapi')
        except AttributeError:
            serpapi_key = None
    if not serpapi_key:
        serpapi_key = current_app.config.get('SERPAPI_API_KEY')

    serp_service = SerpAPISearchService(
        api_key=serpapi_key,
        engine=current_app.config.get('SERPAPI_DEFAULT_ENGINE', 'google'),
        timeout=current_app.config.get('SERPAPI_TIMEOUT', 12)
    )

    return search_service, ai, serp_service


def build_fallback_search_results(query: str, num_results: int, reason: str) -> Dict[str, any]:
    """Generate placeholder search results when live integrations are unavailable."""
    max_items = max(1, min(num_results, 5))
    issued_at = datetime.utcnow()
    results = []
    for index in range(max_items):
        position = index + 1
        results.append({
            'id': f'fallback-{position}',
            'title': f'Insight {position}: {query.title()} snapshot',
            'url': f'https://researchhub.local/mock/{quote_plus(query)}/{position}',
            'snippet': f'Hypothetical finding #{position} generated while live search connectivity is pending. Replace once validation succeeds for "{query}".',
            'author': 'ResearchHub Preview Engine',
            'published_date': (issued_at - timedelta(days=position)).isoformat() + 'Z',
            'score': max(0.3, 1 - (index * 0.12)),
            'source': 'Offline preview'
        })

    return {
        'query': query,
        'answer': f'Preview insights for "{query}" while we finalise live integration validation.',
        'results': results,
        'total_results': len(results),
        'execution_time': 0.01,
        'search_type': 'offline-fallback',
        'timestamp': issued_at.isoformat() + 'Z',
        'fallback': True,
        'fallback_reason': reason
    }


@bp.route('/search', methods=['POST'])
@jwt_required()
@limiter.limit("20 per minute")
def search():
    """
    Perform research search.
    
    Request JSON:
        - query: Search query (required)
        - num_results: Number of results (default: 10)
        - search_type: Type of search (keyword/neural/auto, default: auto)
        - enhance_query: Use AI to enhance query (default: false)
        - project_id: Associated project ID (optional)
        - save_results: Save results to database (default: true)
    
    Returns:
        Search results with metadata
    """
    try:
        user_id = get_jwt_identity()
        user = User.get_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check quota
        if not user.can_search(current_app.config):
            raise QuotaExceededError("Daily search limit exceeded")

        data = request.get_json() or {}
        query_text = data.get('query', '').strip()
        
        if not query_text:
            return jsonify({'error': 'Query is required'}), 400
        
        num_results = min(data.get('num_results', 10), current_app.config['MAX_SEARCH_RESULTS'])
        search_type = (data.get('search_type') or 'auto').lower()
        enhance_query = data.get('enhance_query', False)
        project_id = data.get('project_id')
        save_results = data.get('save_results', True)

        try:
            query_type_enum = QueryType(search_type)
        except ValueError:
            query_type_enum = QueryType.AUTO
        
        # Get services
        search_service, ai, serp_service = get_services(user)
        
        # Enhance query if requested
        enhanced_query = query_text
        if enhance_query and current_app.config.get('ENABLE_AUTO_SUMMARIZATION'):
            enhanced_query = ai.enhance_query(query_text)
        
        orchestrator = SearchOrchestrator(
            providers=[
                OpenAISearchProvider(ai),
                PerplexitySearchProvider(search_service),
                SerpAPISearchProvider(serp_service),
            ],
            fallback_enabled=current_app.config.get('ENABLE_OFFLINE_SEARCH_FALLBACK', True),
            fallback_builder=lambda _query, requested, reason: build_fallback_search_results(query_text, requested, reason),
        )

        search_results, engine_used, engine_attempts, engine_errors, fallback_used = orchestrator.search(
            query=enhanced_query,
            num_results=num_results,
            search_type=search_type,
            enhance_query=enhance_query,
        )

        executed_query = enhanced_query if enhance_query else query_text
        search_results['query'] = query_text
        search_results['executed_query'] = executed_query
        search_results['engine_used'] = engine_used
        search_results['engine_attempts'] = engine_attempts
        search_results['engine_errors'] = engine_errors
        metadata = search_results.setdefault('metadata', {}) if isinstance(search_results, dict) else {}
        metadata.update({
            'engine_used': engine_used,
            'engine_attempts': engine_attempts,
            'engine_errors': engine_errors,
            'executed_query': executed_query,
        })
        if engine_errors:
            fallback_reason = '; '.join(f"{err['provider']}: {err['message']}" for err in engine_errors)
            search_results['fallback_reason'] = fallback_reason
            metadata['fallback_reason'] = fallback_reason
        
        # Update user's search count
        user.increment_search_count()
        user.save()
        
        # Save query and results if requested
        if save_results:
            db_query = Query(
                user_id=user.id,
                project_id=project_id,
                query_text=query_text,
                enhanced_query=enhanced_query if enhance_query else None,
                query_type=query_type_enum,
                num_results=num_results,
                total_results=search_results['total_results'],
                execution_time=search_results['execution_time']
            )
            db_query.save()
            
            # Save individual results
            saved_result_ids = []
            for result_data in search_results['results']:
                published_at = result_data.get('published_date')
                if isinstance(published_at, str) and published_at:
                    try:
                        published_at = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    except ValueError:
                        published_at = None

                result = SearchResult(
                    query_id=db_query.id,
                    title=result_data.get('title', ''),
                    url=result_data.get('url', ''),
                    snippet=result_data.get('snippet', '') or result_data.get('text', ''),
                    author=result_data.get('author'),
                    published_date=published_at,
                    relevance_score=result_data.get('score')
                )
                result.save()

                result_data['id'] = result.id
                result_data['query_result_id'] = result.id
                saved_result_ids.append(result.id)

            search_results['query_id'] = db_query.id
            search_results['result_ids'] = saved_result_ids
        
        # Track analytics
        analytics.track_search(
            query_id=search_results.get('query_id'),
            query_text=query_text,
            result_count=search_results['total_results'],
            execution_time=search_results['execution_time'],
            user_tier=user.tier.value,
            search_domain=engine_used
        )
        
        analytics.track_activity(
            user_id=user.id,
            activity_type='search',
            metadata={
                'query': query_text,
                'results': search_results['total_results'],
                'fallback': fallback_used,
                'engine': engine_used
            }
        )
        
        return jsonify(search_results), 200
        
    except QuotaExceededError as e:
        return jsonify({'error': str(e)}), 429
    except RateLimitError as e:
        return jsonify({'error': str(e)}), 429
    except ExternalAPIError as e:
        return jsonify({'error': str(e)}), 502
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        return jsonify({'error': 'Search failed'}), 500


@bp.route('/queries', methods=['GET'])
@jwt_required()
def get_queries():
    """
    Get user's search history.
    
    Query params:
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20)
        - project_id: Filter by project (optional)
    
    Returns:
        List of queries
    """
    try:
        user_id = get_jwt_identity()
        
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        project_id = request.args.get('project_id', type=int)

        query = Query.query.options(joinedload(Query.project)).filter_by(user_id=user_id)
        
        if project_id:
            query = query.filter_by(project_id=project_id)
        
        pagination = query.order_by(Query.created_at.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'queries': [q.to_dict() for q in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }), 200
        
    except Exception as e:
        logger.error(f"Get queries failed: {str(e)}")
        return jsonify({'error': 'Failed to get queries'}), 500


@bp.route('/queries/<int:query_id>', methods=['GET'])
@jwt_required()
def get_query(query_id):
    """
    Get query details with results.
    
    Returns:
        Query details with results
    """
    try:
        user_id = get_jwt_identity()
        
        query = Query.query.filter_by(id=query_id, user_id=user_id).first()
        
        if not query:
            return jsonify({'error': 'Query not found'}), 404
        
        results = [r.to_dict() for r in query.results]
        
        return jsonify({
            'query': query.to_dict(),
            'results': results
        }), 200
        
    except Exception as e:
        logger.error(f"Get query failed: {str(e)}")
        return jsonify({'error': 'Failed to get query'}), 500


@bp.route('/projects', methods=['GET', 'POST'])
@jwt_required()
def projects():
    """Handle research projects."""
    if request.method == 'POST':
        return create_project()
    else:
        return get_projects()


@bp.route('/projects/<int:project_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def project_detail(project_id):
    """Update or delete a specific research project."""
    if request.method == 'PUT':
        return update_project(project_id)
    return delete_project(project_id)


def create_project():
    """
    Create new research project.
    
    Request JSON:
        - title: Project title (required)
        - description: Project description (optional)
        - category: Project category (optional)
        - keywords: List of keywords (optional)
    
    Returns:
        Created project
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json() or {}
        
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        
        project = ResearchProject(
            user_id=user_id,
            title=title,
            description=data.get('description', ''),
            category=data.get('category'),
            keywords=data.get('keywords', [])
        )
        project.save()
        
        analytics.track_activity(
            user_id=user_id,
            activity_type='project_created',
            resource_type='project',
            resource_id=project.id
        )
        
        return jsonify({
            'message': 'Project created',
            'project': project.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Create project failed: {str(e)}")
        return jsonify({'error': 'Failed to create project'}), 500


def get_projects():
    """
    Get user's projects.
    
    Returns:
        List of projects
    """
    try:
        user_id = get_jwt_identity()
        
        projects = ResearchProject.query.filter_by(user_id=user_id).order_by(
            ResearchProject.created_at.desc()
        ).all()
        
        return jsonify({
            'projects': [p.to_dict() for p in projects]
        }), 200
        
    except Exception as e:
        logger.error(f"Get projects failed: {str(e)}")
        return jsonify({'error': 'Failed to get projects'}), 500


def update_project(project_id):
    """Update an existing project."""
    try:
        user_id = get_jwt_identity()
        project = ResearchProject.query.filter_by(id=project_id, user_id=user_id).first()

        if not project:
            return jsonify({'error': 'Project not found'}), 404

        data = request.get_json() or {}

        if 'title' in data and data['title'].strip():
            project.title = data['title'].strip()
        if 'description' in data:
            project.description = data['description']
        if 'status' in data:
            project.status = data['status']
        if 'category' in data:
            project.category = data['category']
        if 'keywords' in data:
            project.keywords = data['keywords']

        project.save()

        analytics.track_activity(
            user_id=user_id,
            activity_type='project_updated',
            resource_type='project',
            resource_id=project.id
        )

        return jsonify({'message': 'Project updated', 'project': project.to_dict()}), 200

    except Exception as e:
        logger.error(f"Update project failed: {str(e)}")
        return jsonify({'error': 'Failed to update project'}), 500


def delete_project(project_id):
    """Delete a project and associated resources."""
    try:
        user_id = get_jwt_identity()
        project = ResearchProject.query.filter_by(id=project_id, user_id=user_id).first()

        if not project:
            return jsonify({'error': 'Project not found'}), 404

        project.delete()

        analytics.track_activity(
            user_id=user_id,
            activity_type='project_deleted',
            resource_type='project',
            resource_id=project_id
        )

        return jsonify({'message': 'Project deleted'}), 200

    except Exception as e:
        logger.error(f"Delete project failed: {str(e)}")
        return jsonify({'error': 'Failed to delete project'}), 500
