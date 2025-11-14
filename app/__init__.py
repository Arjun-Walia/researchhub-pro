"""Main Flask application factory."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import inspect, text

from config import get_config
from app.models.base import db
from app.services.cache_service import CacheService


# Initialize extensions
jwt = JWTManager()
mail = Mail()
migrate = Migrate()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
cache = None


def create_app(config_name=None):
    """
    Create and configure Flask application.
    
    Args:
        config_name: Configuration name (development, production, testing)
        
    Returns:
        Configured Flask app
    """
    app = Flask(__name__)
    
    # Load configuration
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Setup logging
    setup_logging(app)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    CORS(app, origins=app.config['CORS_ORIGINS'])
    limiter.init_app(app)
    
    # Initialize cache
    global cache
    try:
        cache = CacheService(app.config['REDIS_URL'])
        app.cache = cache
    except Exception as e:
        app.logger.warning(f"Cache initialization failed: {e}")
        cache = None
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register CLI commands
    register_cli_commands(app)
    
    # Create tables
    with app.app_context():
        db.create_all()
        ensure_schema_upgrades(app)
    
    app.logger.info(f"ResearchHub Pro initialized in {config.FLASK_ENV} mode")
    
    return app


def setup_logging(app):
    """Configure application logging."""
    if not app.debug and not app.testing:
        # Create logs directory
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # File handler
        file_handler = RotatingFileHandler(
            app.config['LOG_FILE'],
            maxBytes=10240000,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            app.config['LOG_FORMAT']
        ))
        file_handler.setLevel(getattr(logging, app.config['LOG_LEVEL']))
        
        app.logger.addHandler(file_handler)
        app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL']))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            app.config['LOG_FORMAT']
        ))
        app.logger.addHandler(console_handler)


def register_blueprints(app):
    """Register Flask blueprints."""
    from app.api.v1 import auth, research, collections, analytics, admin, export_api
    from app import routes
    
    # API v1
    app.register_blueprint(auth.bp, url_prefix='/api/v1/auth')
    app.register_blueprint(research.bp, url_prefix='/api/v1/research')
    app.register_blueprint(collections.bp, url_prefix='/api/v1/collections')
    app.register_blueprint(analytics.bp, url_prefix='/api/v1/analytics')
    app.register_blueprint(admin.bp, url_prefix='/api/v1/admin')
    app.register_blueprint(export_api.bp, url_prefix='/api/v1/export')
    
    # Web routes
    app.register_blueprint(routes.bp)


def register_error_handlers(app):
    """Register error handlers."""
    from app.utils.error_handlers import register_handlers
    register_handlers(app)


def register_cli_commands(app):
    """Register CLI commands."""
    from app.cli import register_commands
    register_commands(app)


def ensure_schema_upgrades(app):
    """Apply lightweight schema adjustments for deployments without migrations."""
    try:
        engine = db.engine
        inspector = inspect(engine)
        if 'users' not in inspector.get_table_names():
            return

        column_names = {col['name'] for col in inspector.get_columns('users')}

        with engine.begin() as connection:
            if 'perplexity_api_key' not in column_names:
                connection.execute(text('ALTER TABLE users ADD COLUMN perplexity_api_key VARCHAR(255)'))
            if 'perplexity_key_last_validated_at' not in column_names:
                datetime_type = 'TIMESTAMP'
                if engine.dialect.name == 'sqlite':
                    datetime_type = 'TEXT'
                connection.execute(text(f'ALTER TABLE users ADD COLUMN perplexity_key_last_validated_at {datetime_type}'))
            if 'openai_api_key' not in column_names:
                connection.execute(text('ALTER TABLE users ADD COLUMN openai_api_key VARCHAR(255)'))
            if 'openai_key_last_validated_at' not in column_names:
                datetime_type = 'TIMESTAMP' if engine.dialect.name != 'sqlite' else 'TEXT'
                connection.execute(text(f'ALTER TABLE users ADD COLUMN openai_key_last_validated_at {datetime_type}'))
            if 'anthropic_api_key' not in column_names:
                connection.execute(text('ALTER TABLE users ADD COLUMN anthropic_api_key VARCHAR(255)'))
            if 'anthropic_key_last_validated_at' not in column_names:
                datetime_type = 'TIMESTAMP' if engine.dialect.name != 'sqlite' else 'TEXT'
                connection.execute(text(f'ALTER TABLE users ADD COLUMN anthropic_key_last_validated_at {datetime_type}'))
            if 'serpapi_api_key' not in column_names:
                connection.execute(text('ALTER TABLE users ADD COLUMN serpapi_api_key VARCHAR(255)'))
            if 'serpapi_key_last_validated_at' not in column_names:
                datetime_type = 'TIMESTAMP' if engine.dialect.name != 'sqlite' else 'TEXT'
                connection.execute(text(f'ALTER TABLE users ADD COLUMN serpapi_key_last_validated_at {datetime_type}'))
            if 'gemini_api_key' not in column_names:
                connection.execute(text('ALTER TABLE users ADD COLUMN gemini_api_key VARCHAR(255)'))
            if 'gemini_key_last_validated_at' not in column_names:
                datetime_type = 'TIMESTAMP' if engine.dialect.name != 'sqlite' else 'TEXT'
                connection.execute(text(f'ALTER TABLE users ADD COLUMN gemini_key_last_validated_at {datetime_type}'))

        if 'researchproject' in inspector.get_table_names():
            project_columns = {col['name'] for col in inspector.get_columns('researchproject')}
            with engine.begin() as connection:
                if 'collaborators' not in project_columns:
                    json_type = 'JSON' if engine.dialect.name not in ('sqlite',) else 'TEXT'
                    connection.execute(text(f'ALTER TABLE researchproject ADD COLUMN collaborators {json_type}'))
                if 'timeline' not in project_columns:
                    json_type = 'JSON' if engine.dialect.name not in ('sqlite',) else 'TEXT'
                    connection.execute(text(f'ALTER TABLE researchproject ADD COLUMN timeline {json_type}'))
    except Exception as exc:
        app.logger.warning(f"Schema upgrade skipped: {exc}")


def create_celery_app(app=None):
    """
    Create Celery app for background tasks.
    
    Args:
        app: Flask app instance
        
    Returns:
        Celery app
    """
    from celery import Celery
    
    app = app or create_app()
    
    celery = Celery(
        app.import_name,
        broker=app.config['CELERY_BROKER_URL'],
        backend=app.config['CELERY_RESULT_BACKEND']
    )
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery
