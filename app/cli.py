"""CLI commands for the application."""
import click
from flask.cli import with_appcontext

from app.models.base import db
from app.models import User


def register_commands(app):
    """Register CLI commands with Flask app."""
    
    @app.cli.command()
    @with_appcontext
    def init_db():
        """Initialize the database."""
        db.create_all()
        click.echo('Database initialized.')
    
    @app.cli.command()
    @with_appcontext
    def seed_db():
        """Seed database with sample data."""
        # Create admin user
        admin = User.query.filter_by(email='admin@researchhub.com').first()
        if not admin:
            admin = User(
                email='admin@researchhub.com',
                username='admin',
                first_name='Admin',
                last_name='User',
                role='admin',
                tier='enterprise',
                is_active=True,
                is_verified=True
            )
            admin.set_password('Admin@123')
            admin.save()
            click.echo('Admin user created.')
        else:
            click.echo('Admin user already exists.')
        
        click.echo('Database seeded successfully.')
    
    @app.cli.command()
    @with_appcontext
    def create_admin():
        """Create an admin user interactively."""
        email = click.prompt('Email')
        username = click.prompt('Username')
        password = click.prompt('Password', hide_input=True, confirmation_prompt=True)
        
        if User.query.filter_by(email=email).first():
            click.echo('User with this email already exists.')
            return
        
        admin = User(
            email=email,
            username=username,
            role='admin',
            tier='enterprise',
            is_active=True,
            is_verified=True
        )
        admin.set_password(password)
        admin.save()
        
        click.echo(f'Admin user {username} created successfully.')
