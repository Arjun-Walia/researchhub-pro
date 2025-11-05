"""Base model with common functionality."""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.ext.declarative import declared_attr

db = SQLAlchemy()


class BaseModel(db.Model):
    """Base model with common fields and methods."""
    
    __abstract__ = True
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    @declared_attr
    def __tablename__(cls):
        """Generate table name automatically from class name."""
        return cls.__name__.lower()
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def save(self):
        """Save the current instance."""
        db.session.add(self)
        db.session.commit()
        return self
    
    def delete(self):
        """Delete the current instance."""
        db.session.delete(self)
        db.session.commit()
    
    @classmethod
    def get_by_id(cls, id):
        """Get instance by ID."""
        return cls.query.get(id)
    
    @classmethod
    def get_all(cls, limit=None, offset=None):
        """Get all instances with optional pagination."""
        query = cls.query
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        return query.all()
