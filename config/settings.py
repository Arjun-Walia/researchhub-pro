"""
Configuration settings for ResearchHub Pro.
Supports multiple environments with secure defaults.
"""
import os
from datetime import timedelta
from pathlib import Path


class Config:
    """Base configuration with secure defaults."""
    
    # Application
    APP_NAME = "ResearchHub Pro"
    VERSION = "1.0.0"
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Flask
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = False
    TESTING = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///researchhub.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 20
    }
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Celery
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers', 'cookies']
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_CSRF_PROTECT = True
    
    # External APIs
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
    PERPLEXITY_SHARED_API_KEY = os.getenv('PERPLEXITY_SHARED_API_KEY')
    PERPLEXITY_API_BASE_URL = os.getenv('PERPLEXITY_API_BASE_URL', 'https://api.perplexity.ai')
    PERPLEXITY_DEFAULT_MODEL = os.getenv('PERPLEXITY_DEFAULT_MODEL', 'pplx-70b-online')
    PERPLEXITY_VALIDATE_KEYS = os.getenv('PERPLEXITY_VALIDATE_KEYS', 'true').lower() not in {'0', 'false', 'no'}
    PERPLEXITY_VALIDATION_TIMEOUT = int(os.getenv('PERPLEXITY_VALIDATION_TIMEOUT', '8'))
    
    # Rate Limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URL = REDIS_URL
    RATELIMIT_STRATEGY = 'fixed-window'
    DEFAULT_RATE_LIMIT = "100/hour"
    
    # File Upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = Path('uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx', 'csv', 'json'}
    
    # Email (for notifications)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@researchhub.com')
    
    # Security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = 'logs/researchhub.log'
    
    # Monitoring
    SENTRY_DSN = os.getenv('SENTRY_DSN')
    ENABLE_METRICS = True
    
    # Research Settings
    DEFAULT_SEARCH_RESULTS = 10
    MAX_SEARCH_RESULTS = 100
    SEARCH_TIMEOUT = 30
    ENABLE_AUTO_SUMMARIZATION = True
    ENABLE_CITATION_GENERATION = True
    
    # User Tiers
    USER_TIERS = {
        'free': {
            'daily_searches': 10,
            'max_collections': 5,
            'max_storage_mb': 100,
            'ai_features': False
        },
        'pro': {
            'daily_searches': 100,
            'max_collections': 50,
            'max_storage_mb': 1000,
            'ai_features': True
        },
        'enterprise': {
            'daily_searches': -1,  # unlimited
            'max_collections': -1,
            'max_storage_mb': 10000,
            'ai_features': True
        }
    }


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    FLASK_ENV = 'development'
    SESSION_COOKIE_SECURE = False
    JWT_COOKIE_SECURE = False
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Production environment configuration."""
    FLASK_ENV = 'production'
    DEBUG = False
    
    # Enforce HTTPS
    PREFERRED_URL_SCHEME = 'https'
    
    # Stricter security
    SESSION_COOKIE_SECURE = True
    JWT_COOKIE_SECURE = True
    
    # Production database should use PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://user:password@localhost/researchhub'
    )


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    
    # Use mock services in tests
    PERPLEXITY_API_KEY = 'test-key'
    OPENAI_API_KEY = 'test-key'
    PERPLEXITY_VALIDATE_KEYS = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """Get configuration based on environment."""
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])
