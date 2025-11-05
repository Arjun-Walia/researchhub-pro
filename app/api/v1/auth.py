"""Authentication API endpoints."""
from datetime import datetime
from typing import Optional, Dict, Any

import logging
import requests
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required
)
from sqlalchemy import or_, func

from app.utils.jwt_helpers import get_current_user_id
from app.models import User, ResearchProject, Query, Collection, IntegrationEvent, OAuthConnection
from app.services.email_service import EmailService
from app.services.analytics_service import AnalyticsService
from app.services.perplexity_service import PerplexityService, PerplexityValidationError
from app.utils.validators import validate_email, validate_password
from app import limiter


bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)
analytics = AnalyticsService()
INTEGRATION_METADATA: Dict[str, Dict[str, Any]] = {
    'perplexity': {
        'field': 'perplexity_api_key',
        'label': 'Perplexity',
        'capabilities': ['search', 'ai-assist'],
        'validation_timeout': lambda app: app.config.get('PERPLEXITY_VALIDATION_TIMEOUT', 8)
    },
    'openai': {
        'field': 'openai_api_key',
        'label': 'OpenAI',
        'capabilities': ['ai-models', 'embeddings'],
        'validation_timeout': lambda app: app.config.get('INTEGRATION_VALIDATION_TIMEOUT', 8)
    },
    'anthropic': {
        'field': 'anthropic_api_key',
        'label': 'Anthropic',
        'capabilities': ['ai-models'],
        'validation_timeout': lambda app: app.config.get('INTEGRATION_VALIDATION_TIMEOUT', 8)
    },
    'serpapi': {
        'field': 'serpapi_api_key',
        'label': 'SerpAPI',
        'capabilities': ['web-enrichment', 'search'],
        'validation_timeout': lambda app: app.config.get('INTEGRATION_VALIDATION_TIMEOUT', 8)
    }
}

GENERIC_INTEGRATIONS = {
    provider: meta['field']
    for provider, meta in INTEGRATION_METADATA.items()
    if provider != 'perplexity'
}


class IntegrationValidationError(Exception):
    """Raised when a non-Perplexity provider rejects an API key."""


def compute_integration_capabilities(user: User) -> Dict[str, Any]:
    """Return feature flags unlocked by active integrations."""
    active = {
        provider: user.is_integration_connected(provider)
        for provider in INTEGRATION_METADATA.keys()
    }
    labels = {
        provider: INTEGRATION_METADATA.get(provider, {}).get('label', provider.title())
        for provider in INTEGRATION_METADATA.keys()
    }

    powered_by = [labels[p] for p, flag in active.items() if flag]
    ai_models = [labels[p] for p in ('openai', 'anthropic') if active.get(p)]
    enrichment = [labels[p] for p in ('serpapi',) if active.get(p)]

    return {
        'powered_by': powered_by,
        'search_provider': labels['perplexity'] if active.get('perplexity') else None,
        'ai_model_providers': ai_models,
        'enrichment_providers': enrichment,
        'has_premium_search': active.get('perplexity', False),
        'has_premium_ai': any(active.get(p) for p in ('openai', 'anthropic')),
        'has_enrichment': any(enrichment)
    }


def record_integration_event(user: User, provider: str, action: str, status: str, message: str, metadata: Optional[Dict[str, Any]] = None):
    """Persist an integration audit event while guarding against failures."""
    try:
        IntegrationEvent.record(
            user_id=user.id,
            provider=provider,
            action=action,
            status=status,
            message=message,
            metadata=metadata or {}
        )
    except Exception as exc:  # pragma: no cover - logging only
        logger.warning("Failed to record integration event for %s: %s", provider, exc)


def _validate_openai_key(api_key: str, timeout: int) -> Dict[str, Any]:
    headers = {
        'Authorization': f'Bearer {api_key}',
    }
    try:
        response = requests.get('https://api.openai.com/v1/models', headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise IntegrationValidationError('Unable to reach OpenAI for validation. Please try again.') from exc

    if response.status_code == 401:
        raise IntegrationValidationError('OpenAI rejected the API key. Double-check and try again.')
    if response.status_code >= 400:
        raise IntegrationValidationError('OpenAI validation is unavailable right now. Retry shortly.')

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    models = payload.get('data', [])
    model_count = len(models) if isinstance(models, list) else 0
    return {
        'status': 'linked',
        'model_count': model_count,
        'raw': payload if isinstance(payload, dict) else {}
    }


def _validate_anthropic_key(api_key: str, timeout: int) -> Dict[str, Any]:
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01'
    }
    try:
        response = requests.get('https://api.anthropic.com/v1/models', headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise IntegrationValidationError('Unable to reach Anthropic for validation.') from exc

    if response.status_code == 401:
        raise IntegrationValidationError('Anthropic rejected the API key. Confirm the value and try again.')
    if response.status_code >= 400:
        raise IntegrationValidationError('Anthropic validation is currently unavailable. Please retry later.')

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    models = payload.get('data') or payload.get('models') or []
    if isinstance(models, dict):
        models = list(models.values())
    model_count = len(models) if isinstance(models, list) else 0
    return {
        'status': 'linked',
        'model_count': model_count,
        'raw': payload if isinstance(payload, dict) else {}
    }


def _validate_serpapi_key(api_key: str, timeout: int) -> Dict[str, Any]:
    params = {'api_key': api_key}
    try:
        response = requests.get('https://serpapi.com/account', params=params, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise IntegrationValidationError('Unable to reach SerpAPI for validation. Check connectivity and retry.') from exc

    if response.status_code == 401:
        raise IntegrationValidationError('SerpAPI reported the key as invalid. Please verify and resubmit.')
    if response.status_code >= 400:
        raise IntegrationValidationError('SerpAPI validation endpoint is unavailable. Try again shortly.')

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if isinstance(payload, dict) and payload.get('error'):
        raise IntegrationValidationError(payload.get('error'))

    plan_name = payload.get('plan_name') if isinstance(payload, dict) else None
    requests_left = payload.get('plan_searches_left') if isinstance(payload, dict) else None
    return {
        'status': 'linked',
        'plan': plan_name,
        'requests_left': requests_left,
        'raw': payload if isinstance(payload, dict) else {}
    }


VALIDATION_HANDLERS = {
    'openai': _validate_openai_key,
    'anthropic': _validate_anthropic_key,
    'serpapi': _validate_serpapi_key
}


def validate_integration_key(provider: str, api_key: Optional[str]) -> Dict[str, Any]:
    """Validate the supplied API key against the provider-specific endpoint."""
    if not api_key:
        raise IntegrationValidationError('API key is required for validation.')

    provider = provider.lower()
    handler = VALIDATION_HANDLERS.get(provider)
    if not handler:
        # Unknown providers are accepted optimistically but recorded as pending validation.
        return {'status': 'linked', 'raw': {}, 'note': 'No validator available'}

    timeout_config = INTEGRATION_METADATA.get(provider, {}).get('validation_timeout')
    timeout = timeout_config(current_app) if callable(timeout_config) else current_app.config.get('INTEGRATION_VALIDATION_TIMEOUT', 8)
    return handler(api_key, timeout)


def build_user_payload(user: User, include_sensitive: bool = False) -> dict:
    """Serialize user with enriched usage metrics and tier limits."""
    base_payload = user.to_dict(include_sensitive=include_sensitive)

    tier_limits = current_app.config.get('USER_TIERS', {}).get(user.tier.value, {})
    search_limit = tier_limits.get('daily_searches')

    project_count = ResearchProject.query.filter_by(user_id=user.id).count()
    collection_count = Collection.query.filter_by(user_id=user.id).count()
    total_queries = Query.query.filter_by(user_id=user.id).count()

    base_payload.update({
        'project_count': project_count,
        'collection_count': collection_count,
        'total_queries': total_queries,
        'search_limit': search_limit,
        'tier_features': tier_limits.copy() if isinstance(tier_limits, dict) else {},
    })

    base_payload['usage'] = {
        'searches_today': base_payload.get('searches_today') or user.searches_today or 0,
        'search_limit': search_limit,
        'projects_total': project_count,
        'collections_total': collection_count,
        'queries_total': total_queries,
        'login_count': base_payload.get('login_count', user.login_count or 0)
    }

    events_map = base_payload.get('integration_events', {}) or {}
    trimmed_events = {
        provider: events[:8]
        for provider, events in events_map.items()
    }
    base_payload['integration_events'] = trimmed_events

    base_payload['integration_capabilities'] = compute_integration_capabilities(user)



def apply_perplexity_api_key(user: User, api_key: Optional[str]):
    """Validate and persist a Perplexity API key for the provided user."""
    key = (api_key or '').strip()

    existing_plain = user.get_integration_key('perplexity') if user.perplexity_api_key else None

    if not key:
        if existing_plain:
            user.clear_perplexity_api_key()
            user.save()
            record_integration_event(user, 'perplexity', 'remove', 'success', 'Perplexity key removed')
            return {
                'status': 'removed',
                'connected': False,
                'just_linked': False,
                'last_validated_at': None
            }
        return None

    validate_keys = current_app.config.get('PERPLEXITY_VALIDATE_KEYS', True)
    should_validate = validate_keys and (existing_plain != key or not user.perplexity_key_last_validated_at)

    service = PerplexityService(
        api_key=key,
        base_url=current_app.config.get('PERPLEXITY_API_BASE_URL'),
        timeout=current_app.config.get('PERPLEXITY_VALIDATION_TIMEOUT', 8),
        validate=should_validate
    )

    try:
        result = service.validate_key()
    except PerplexityValidationError as exc:
        record_integration_event(user, 'perplexity', 'validate', 'error', str(exc))
        raise

    user.set_perplexity_api_key(key, validated=True)
    user.save()

    response_payload = result.to_dict()
    response_payload.pop('raw', None)
    response_payload.update({
        'connected': True,
        'just_linked': existing_plain != key,
        'last_validated_at': user.perplexity_key_last_validated_at.isoformat() if user.perplexity_key_last_validated_at else None
    })

    record_integration_event(
        user,
        'perplexity',
        'validate',
        'success',
        'Perplexity key linked',
        metadata={
            'models_detected': response_payload.get('models_detected'),
            'just_linked': response_payload.get('just_linked')
        }
    )

    return response_payload


def apply_generic_api_key(user: User, provider: str, api_key: Optional[str]):
    """Persist API keys for providers that do not require live validation."""
    key = (api_key or '').strip()

    if not key:
        user.update_integration_key(provider, None)
        user.save()
        record_integration_event(user, provider, 'remove', 'success', f'{INTEGRATION_METADATA.get(provider, {}).get("label", provider.title())} key removed')
        return {
            'connected': False,
            'status': 'not_configured',
            'last_validated_at': None
        }

    try:
        validation = validate_integration_key(provider, key)
    except IntegrationValidationError as exc:
        record_integration_event(
            user,
            provider,
            'validate',
            'error',
            str(exc)
        )
        raise
    user.update_integration_key(provider, key)
    user.save()
    stamp_attr = f"{provider}_key_last_validated_at"
    timestamp = getattr(user, stamp_attr, None)

    response = {
        'connected': True,
        'status': validation.get('status', 'linked'),
        'last_validated_at': timestamp.isoformat() if timestamp else None,
        'metadata': {k: v for k, v in validation.items() if k not in {'status', 'raw'}}
    }

    record_integration_event(
        user,
        provider,
        'validate',
        'success',
        f"{INTEGRATION_METADATA.get(provider, {}).get('label', provider.title())} key linked",
        metadata=response.get('metadata')
    )

    return response


@bp.route('/register', methods=['POST'])
@limiter.limit("5 per hour")
def register():
    """
    Register a new user.
    
    Request JSON:
        - email: User email
        - username: Username
        - password: Password
        - first_name: First name (optional)
        - last_name: Last name (optional)
    
    Returns:
        User data and tokens
    """
    try:
        data = request.get_json() or {}
        
        # Validate input
        email = data.get('email', '').strip().lower()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        perplexity_key = (data.get('perplexity_api_key') or '').strip()
        
        if not email or not username or not password:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Validate email format
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate password strength
        password_valid, password_message = validate_password(password)
        if not password_valid:
            return jsonify({'error': password_message}), 400
        
        # Check if user exists
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 409
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already taken'}), 409
        
        # Create user
        user = User(
            email=email,
            username=username,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            organization=data.get('organization', '')
        )
        user.set_password(password)
        perplexity_feedback = None
        integration_feedback = {}
        if perplexity_key:
            try:
                perplexity_feedback = apply_perplexity_api_key(user, perplexity_key)
            except PerplexityValidationError as exc:
                return jsonify({'error': str(exc)}), 400

        for provider, field in GENERIC_INTEGRATIONS.items():
            if field in data:
                try:
                    integration_feedback[provider] = apply_generic_api_key(user, provider, data.get(field))
                except IntegrationValidationError as exc:
                    return jsonify({'error': str(exc), 'provider': provider}), 400

        user.save()
        
        # Track activity
        analytics.track_activity(
            user_id=user.id,
            activity_type='registration',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        logger.info(f"New user registered: {username}")
        
        response_body = {
            'message': 'Registration successful',
            'user': build_user_payload(user, include_sensitive=True),
            'access_token': access_token,
            'refresh_token': refresh_token
        }

        if perplexity_feedback:
            response_body['perplexity_integration'] = perplexity_feedback

        if integration_feedback:
            response_body.setdefault('integration_updates', {}).update(integration_feedback)

        return jsonify(response_body), 201
        
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500


@bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """
    Authenticate user and return tokens.
    
    Request JSON:
        - email: User email or username
        - password: Password
    
    Returns:
        User data and tokens
    """
    try:
        data = request.get_json() or {}
        
        identifier = (data.get('email') or '').strip()
        password = data.get('password', '')
        perplexity_key = (data.get('perplexity_api_key') or '').strip()
        
        if not identifier or not password:
            return jsonify({'error': 'Missing credentials'}), 400
        
        # Find user by email or username
        user = User.query.filter(
            or_(
                User.email == identifier.lower(),
                func.lower(User.username) == identifier.lower()
            )
        ).first()
        
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check if account is locked
        if user.is_account_locked():
            return jsonify({'error': 'Account temporarily locked'}), 403
        
        # Verify password
        if not user.check_password(password):
            user.increment_login_attempts()
            user.save()
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check if account is active
        if not user.is_active:
            return jsonify({'error': 'Account deactivated'}), 403
        
        # Successful login
        user.reset_login_attempts()

        perplexity_feedback = None
        integration_feedback = {}
        if perplexity_key:
            try:
                perplexity_feedback = apply_perplexity_api_key(user, perplexity_key)
            except PerplexityValidationError as exc:
                return jsonify({'error': str(exc)}), 400

        for provider, field in GENERIC_INTEGRATIONS.items():
            if field in data:
                try:
                    integration_feedback[provider] = apply_generic_api_key(user, provider, data.get(field))
                except IntegrationValidationError as exc:
                    return jsonify({'error': str(exc), 'provider': provider}), 400

        user.save()
        
        # Track activity
        analytics.track_activity(
            user_id=user.id,
            activity_type='login',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        
        # Create tokens
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        response_body = {
            'message': 'Login successful',
            'user': build_user_payload(user, include_sensitive=True),
            'access_token': access_token,
            'refresh_token': refresh_token
        }

        if perplexity_feedback:
            response_body['perplexity_integration'] = perplexity_feedback

        if integration_feedback:
            response_body.setdefault('integration_updates', {}).update(integration_feedback)

        return jsonify(response_body), 200
        
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500


@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access token using refresh token.
    
    Returns:
        New access token
    """
    try:
        user_id = get_current_user_id()
        if user_id is None:
            return jsonify({'error': 'Invalid token subject'}), 401

        access_token = create_access_token(identity=str(user_id))
        
        return jsonify({
            'access_token': access_token
        }), 200
        
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        return jsonify({'error': 'Token refresh failed'}), 500


@bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Get current authenticated user.
    
    Returns:
        User data
    """
    try:
        user_id = get_current_user_id()
        if user_id is None:
            return jsonify({'error': 'Invalid token subject'}), 401

        user = User.get_by_id(user_id)

        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'user': build_user_payload(user, include_sensitive=True)
        }), 200

    except Exception as e:
        logger.error(f"Get current user failed: {str(e)}")
        return jsonify({'error': 'Failed to get user'}), 500


@bp.route('/me', methods=['PUT'])
@jwt_required()
def update_profile():
    """
    Update user profile.
    
    Request JSON:
        - first_name: First name (optional)
        - last_name: Last name (optional)
        - bio: Bio (optional)
        - organization: Organization (optional)
    
    Returns:
        Updated user data
    """
    try:
        user_id = get_current_user_id()
        if user_id is None:
            return jsonify({'error': 'Invalid token subject'}), 401

        user = User.get_by_id(user_id)

        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json() or {}
        
        # Update allowed fields
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'bio' in data:
            user.bio = data['bio']
        if 'organization' in data:
            user.organization = data['organization']

        perplexity_feedback = None
        integration_feedback = {}
        if 'perplexity_api_key' in data:
            try:
                perplexity_feedback = apply_perplexity_api_key(user, data.get('perplexity_api_key'))
            except PerplexityValidationError as exc:
                return jsonify({'error': str(exc)}), 400

        for provider, field in GENERIC_INTEGRATIONS.items():
            if field in data:
                try:
                    integration_feedback[provider] = apply_generic_api_key(user, provider, data.get(field))
                except IntegrationValidationError as exc:
                    return jsonify({'error': str(exc), 'provider': provider}), 400
        
        user.save()
        
        # Track activity
        analytics.track_activity(
            user_id=user.id,
            activity_type='profile_update'
        )
        
        response_payload = {
            'message': 'Profile updated',
            'user': build_user_payload(user, include_sensitive=True)
        }

        if perplexity_feedback is not None:
            response_payload['perplexity_integration'] = perplexity_feedback

        if integration_feedback:
            response_payload['integration_updates'] = integration_feedback

        return jsonify(response_payload), 200
        
    except Exception as e:
        logger.error(f"Profile update failed: {str(e)}")
        return jsonify({'error': 'Profile update failed'}), 500


@bp.route('/oauth/<provider>', methods=['POST'])
@jwt_required()
def connect_oauth_provider(provider: str):
    """Simulate connecting an OAuth provider and persist the connection state."""
    try:
        user_id = get_current_user_id()
        if user_id is None:
            return jsonify({'error': 'Invalid token subject'}), 401

        user = User.get_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json() or {}
        provider = provider.lower()
        label = data.get('label') or provider.title()
        scopes = data.get('scopes') or []

        connection = user.get_oauth_connection(provider)
        if not connection:
            connection = OAuthConnection(user_id=user.id, provider=provider, label=label)

        connection.mark_connected(
            external_id=data.get('external_id') or f"sim-{provider}-{int(datetime.utcnow().timestamp())}",
            metadata={
                'scopes': scopes,
                'connected_via': 'settings-panel',
                'note': data.get('note')
            }
        )
        connection.save()

        record_integration_event(
            user,
            f'oauth-{provider}',
            'connect',
            'success',
            f'{label} connected',
            metadata={'scopes': scopes}
        )

        return jsonify({
            'message': f'{label} connected',
            'connection': connection.to_dict(),
            'user': build_user_payload(user, include_sensitive=True)
        }), 200

    except Exception as exc:
        logger.error("OAuth connect failed for %s: %s", provider, exc)
        return jsonify({'error': 'Failed to connect provider'}), 500


@bp.route('/oauth/<provider>', methods=['DELETE'])
@jwt_required()
def disconnect_oauth_provider(provider: str):
    """Disconnect an OAuth provider."""
    try:
        user_id = get_current_user_id()
        if user_id is None:
            return jsonify({'error': 'Invalid token subject'}), 401

        user = User.get_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        provider = provider.lower()
        connection = user.get_oauth_connection(provider)
        if not connection:
            return jsonify({'error': 'Connection not found'}), 404

        data = request.get_json() or {}
        reason = data.get('reason')
        connection.mark_disconnected(reason=reason)
        connection.save()

        record_integration_event(
            user,
            f'oauth-{provider}',
            'disconnect',
            'success',
            f'{connection.label or provider.title()} disconnected',
            metadata={'reason': reason} if reason else None
        )

        return jsonify({
            'message': f'{connection.label or provider.title()} disconnected',
            'connection': connection.to_dict(),
            'user': build_user_payload(user, include_sensitive=True)
        }), 200

    except Exception as exc:
        logger.error("OAuth disconnect failed for %s: %s", provider, exc)
        return jsonify({'error': 'Failed to disconnect provider'}), 500


@bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    Change user password.
    
    Request JSON:
        - current_password: Current password
        - new_password: New password
    
    Returns:
        Success message
    """
    try:
        user_id = get_current_user_id()
        if user_id is None:
            return jsonify({'error': 'Invalid token subject'}), 401

        user = User.get_by_id(user_id)

        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json() or {}
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')

        # Verify current password
        if not user.check_password(current_password):
            return jsonify({'error': 'Invalid current password'}), 401

        # Validate new password
        password_valid, password_message = validate_password(new_password)
        if not password_valid:
            return jsonify({'error': password_message}), 400

        # Update password
        user.set_password(new_password)
        user.save()

        # Track activity
        analytics.track_activity(
            user_id=user.id,
            activity_type='password_change'
        )

        return jsonify({
            'message': 'Password changed successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Password change failed: {str(e)}")
        return jsonify({'error': 'Password change failed'}), 500


@bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Logout user (client should discard tokens).
    
    Returns:
        Success message
    """
    try:
        user_id = get_current_user_id()
        if user_id is None:
            return jsonify({'error': 'Invalid token subject'}), 401

        # Track activity
        analytics.track_activity(
            user_id=user_id,
            activity_type='logout'
        )

        return jsonify({
            'message': 'Logout successful'
        }), 200
        
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500


@bp.route('/password/forgot', methods=['POST'])
@limiter.limit("5 per hour")
def forgot_password():
    """Initiate password reset flow."""
    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()

        if not email:
            return jsonify({'error': 'Email is required'}), 400

        user = User.query.filter_by(email=email).first()

        if not user:
            # Do not leak whether the account exists
            return jsonify({'message': 'If an account exists, we sent reset instructions.'}), 200

        token = user.generate_password_reset()
        user.save()

        frontend_base = current_app.config.get('FRONTEND_URL') or request.host_url.rstrip('/')
        reset_link = f"{frontend_base}/reset-password?token={token}"

        mail_extension = current_app.extensions.get('mail') if hasattr(current_app, 'extensions') else None
        EmailService(mail_extension).send_password_reset_email(user.email, reset_link)

        analytics.track_activity(
            user_id=user.id,
            activity_type='password_reset_requested'
        )

        return jsonify({'message': 'If an account exists, we sent reset instructions.'}), 200

    except Exception as e:
        logger.error(f"Password reset request failed: {str(e)}")
        return jsonify({'error': 'Failed to process request'}), 500


@bp.route('/password/reset', methods=['POST'])
@limiter.limit("5 per hour")
def reset_password():
    """Complete password reset using token."""
    try:
        data = request.get_json() or {}
        token = data.get('token')
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')

        if not token or not password:
            return jsonify({'error': 'Token and password are required'}), 400

        if password != confirm_password:
            return jsonify({'error': 'Passwords do not match'}), 400

        password_valid, password_message = validate_password(password)
        if not password_valid:
            return jsonify({'error': password_message}), 400

        user = User.query.filter_by(password_reset_token=token).first()
        if not user or not user.verify_password_reset_token(token):
            return jsonify({'error': 'Invalid or expired reset token'}), 400

        user.set_password(password)
        user.clear_password_reset()
        user.save()

        analytics.track_activity(
            user_id=user.id,
            activity_type='password_reset_completed'
        )

        return jsonify({'message': 'Password reset successfully'}), 200

    except Exception as e:
        logger.error(f"Password reset failed: {str(e)}")
        return jsonify({'error': 'Failed to reset password'}), 500
