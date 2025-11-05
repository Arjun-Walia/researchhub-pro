"""User model and authentication."""
from datetime import datetime, timedelta
import secrets
from typing import Optional
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, String, Boolean, Enum, Integer, DateTime
from sqlalchemy.orm import relationship
import enum

from .base import BaseModel, db
from app.utils.crypto import encrypt_value, decrypt_value


class UserRole(enum.Enum):
    """User roles for RBAC."""
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"
    RESEARCHER = "researcher"


class UserTier(enum.Enum):
    """User subscription tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(BaseModel):
    """User model with authentication and profile."""
    
    __tablename__ = 'users'
    
    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Profile
    first_name = Column(String(100))
    last_name = Column(String(100))
    organization = Column(String(200))
    bio = Column(String(500))
    avatar_url = Column(String(500))
    
    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime)
    
    # Role and tier
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    tier = Column(Enum(UserTier), default=UserTier.FREE, nullable=False)
    
    # Usage tracking
    last_login_at = Column(DateTime)
    login_count = Column(Integer, default=0)
    searches_today = Column(Integer, default=0)
    last_search_date = Column(DateTime)

    # Integrations
    perplexity_api_key = Column(String(255))
    perplexity_key_last_validated_at = Column(DateTime)
    openai_api_key = Column(String(255))
    openai_key_last_validated_at = Column(DateTime)
    anthropic_api_key = Column(String(255))
    anthropic_key_last_validated_at = Column(DateTime)
    serpapi_api_key = Column(String(255))
    serpapi_key_last_validated_at = Column(DateTime)
    
    # Security
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)
    password_reset_token = Column(String(255))
    password_reset_expires = Column(DateTime)
    
    # Relationships
    research_projects = relationship('ResearchProject', back_populates='user', cascade='all, delete-orphan')
    queries = relationship('Query', back_populates='user', cascade='all, delete-orphan')
    collections = relationship('Collection', back_populates='user', cascade='all, delete-orphan')
    team_memberships = relationship('TeamMember', back_populates='user', cascade='all, delete-orphan')
    activities = relationship('UserActivity', back_populates='user', cascade='all, delete-orphan')
    integration_events = relationship('IntegrationEvent', back_populates='user', cascade='all, delete-orphan', order_by='IntegrationEvent.created_at.desc()')
    oauth_connections = relationship('OAuthConnection', back_populates='user', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against hash."""
        return check_password_hash(self.password_hash, password)
    
    def is_account_locked(self):
        """Check if account is locked due to failed login attempts."""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False
    
    def increment_login_attempts(self):
        """Increment failed login attempts and lock if needed."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.utcnow() + timedelta(minutes=30)
    
    def reset_login_attempts(self):
        """Reset failed login attempts on successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login_at = datetime.utcnow()
        self.login_count += 1
    
    def can_search(self, config):
        """Check if user can perform more searches today."""
        tier_limits = config['USER_TIERS'][self.tier.value]
        daily_limit = tier_limits['daily_searches']
        
        if daily_limit == -1:  # Unlimited
            return True
        
        # Reset counter if it's a new day
        if not self.last_search_date or self.last_search_date.date() < datetime.utcnow().date():
            self.searches_today = 0
            self.last_search_date = datetime.utcnow()
        
        return self.searches_today < daily_limit
    
    def increment_search_count(self):
        """Increment today's search count."""
        if not self.last_search_date or self.last_search_date.date() < datetime.utcnow().date():
            self.searches_today = 0
        
        self.searches_today += 1
        self.last_search_date = datetime.utcnow()

    def set_perplexity_api_key(self, api_key: str, validated: bool = False):
        """Store Perplexity API key and optionally stamp validation time."""
        self.perplexity_api_key = encrypt_value(api_key)
        if validated:
            self.perplexity_key_last_validated_at = datetime.utcnow()

    def clear_perplexity_api_key(self):
        """Remove stored Perplexity API credentials."""
        self.perplexity_api_key = None
        self.perplexity_key_last_validated_at = None

    def update_integration_key(self, provider: str, api_key: Optional[str]):
        """Store or clear API credentials for supported providers."""
        provider = provider.lower()
        key_attr = f"{provider}_api_key"
        stamp_attr = f"{provider}_key_last_validated_at"

        if not hasattr(self, key_attr):
            raise AttributeError(f"Unsupported integration provider '{provider}'")

        setattr(self, key_attr, encrypt_value(api_key) if api_key else None)

        if hasattr(self, stamp_attr):
            setattr(self, stamp_attr, datetime.utcnow() if api_key else None)

    def get_integration_key(self, provider: str) -> Optional[str]:
        """Return decrypted API credentials for a provider if present."""
        provider = provider.lower()
        key_attr = f"{provider}_api_key"
        if not hasattr(self, key_attr):
            raise AttributeError(f"Unsupported integration provider '{provider}'")
        return decrypt_value(getattr(self, key_attr))

    def is_integration_connected(self, provider: str) -> bool:
        """Check whether a provider has an active key configured."""
        try:
            return bool(self.get_integration_key(provider))
        except AttributeError:
            return False

    def get_oauth_connection(self, provider: str):
        """Fetch the oauth connection object for a provider, if any."""
        provider = provider.lower()
        return next((conn for conn in self.oauth_connections if conn.provider == provider), None)
    
    def generate_password_reset(self, expires_in=3600):
        """Generate a password reset token and expiry."""
        token = secrets.token_urlsafe(48)
        self.password_reset_token = token
        self.password_reset_expires = datetime.utcnow() + timedelta(seconds=expires_in)
        return token

    def verify_password_reset_token(self, token):
        """Validate provided password reset token."""
        if not token or not self.password_reset_token:
            return False
        if self.password_reset_token != token:
            return False
        if self.password_reset_expires and self.password_reset_expires < datetime.utcnow():
            return False
        return True

    def clear_password_reset(self):
        """Clear password reset token state."""
        self.password_reset_token = None
        self.password_reset_expires = None

    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary."""
        data = {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'organization': self.organization,
            'bio': self.bio,
            'avatar_url': self.avatar_url,
            'role': self.role.value,
            'tier': self.tier.value,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
        }
        
        if include_sensitive:
            data.update({
                'searches_today': self.searches_today,
                'login_count': self.login_count,
            })

        integrations = {}
        for provider in ('perplexity', 'openai', 'anthropic', 'serpapi'):
            stamp_attr = f'{provider}_key_last_validated_at'
            stamp = getattr(self, stamp_attr, None)
            integrations[provider] = {
                'connected': self.is_integration_connected(provider),
                'status': 'linked' if self.is_integration_connected(provider) else 'not_configured',
                'last_validated_at': stamp.isoformat() if stamp else None
            }

        data['integrations'] = integrations

        events_by_provider = {}
        for event in self.integration_events[:40]:
            events_by_provider.setdefault(event.provider, []).append(event.to_dict())
        data['integration_events'] = events_by_provider

        oauth_payload = {}
        for connection in self.oauth_connections:
            oauth_payload[connection.provider] = connection.to_dict()
        data['oauth_connections'] = oauth_payload
        
        return data
    
    def __repr__(self):
        return f'<User {self.username}>'
