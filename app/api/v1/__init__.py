"""API v1 blueprint initialization."""
from flask import Blueprint

# Import blueprints to ensure they're registered
from . import auth, research, collections, analytics, admin, export_api

__all__ = ['auth', 'research', 'collections', 'analytics', 'admin', 'export_api']
