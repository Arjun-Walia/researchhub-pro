"""Analytics and metrics models."""
from sqlalchemy import Column, String, Integer, Float, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship

from .base import BaseModel, db


class UserActivity(BaseModel):
    """Track user activities for analytics."""
    
    __tablename__ = 'useractivity'
    
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    activity_type = Column(String(50), nullable=False)  # search, export, login, etc.
    resource_type = Column(String(50))
    resource_id = Column(Integer)
    
    activity_data = Column(JSON)  # Additional activity data (renamed from metadata)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Relationships
    user = relationship('User', back_populates='activities')
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_user_activity_type', 'user_id', 'activity_type'),
        Index('idx_activity_created', 'created_at'),
    )
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'activity_type': self.activity_type,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'activity_data': self.activity_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SearchAnalytics(BaseModel):
    """Analytics for search queries and performance."""
    
    __tablename__ = 'searchanalytics'
    
    query_id = Column(Integer, ForeignKey('query.id', ondelete='CASCADE'))
    
    # Query metrics
    query_text = Column(db.Text, nullable=False)
    result_count = Column(Integer, default=0)
    execution_time = Column(Float)
    
    # User interaction
    clicks = Column(Integer, default=0)
    avg_time_on_results = Column(Float)
    results_exported = Column(Integer, default=0)
    
    # Quality metrics
    relevance_feedback = Column(Float)  # User feedback on result quality
    
    # Context
    user_tier = Column(String(50))
    search_domain = Column(String(100))
    
    __table_args__ = (
        Index('idx_search_created', 'created_at'),
        Index('idx_search_domain', 'search_domain'),
    )
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'query_text': self.query_text,
            'result_count': self.result_count,
            'execution_time': self.execution_time,
            'clicks': self.clicks,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SystemMetrics(BaseModel):
    """System-wide metrics and health indicators."""
    
    __tablename__ = 'systemmetrics'
    
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(50))
    
    # Categorization
    category = Column(String(50))  # performance, usage, errors, etc.
    tags = Column(JSON)
    
    __table_args__ = (
        Index('idx_metric_name_created', 'metric_name', 'created_at'),
        Index('idx_metric_category', 'category'),
    )
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'metric_unit': self.metric_unit,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
