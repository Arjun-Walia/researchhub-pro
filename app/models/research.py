"""Research-related models."""
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, ForeignKey, Table, JSON
from sqlalchemy.orm import relationship
import enum

from .base import BaseModel, db


# Association tables for many-to-many relationships
result_tags = Table(
    'result_tags',
    db.Model.metadata,
    Column('result_id', Integer, ForeignKey('searchresult.id', ondelete='CASCADE')),
    Column('tag_id', Integer, ForeignKey('tag.id', ondelete='CASCADE'))
)

collection_results = Table(
    'collection_results',
    db.Model.metadata,
    Column('collection_id', Integer, ForeignKey('collection.id', ondelete='CASCADE')),
    Column('result_id', Integer, ForeignKey('searchresult.id', ondelete='CASCADE'))
)


class QueryType(enum.Enum):
    """Types of search queries."""
    KEYWORD = "keyword"
    NEURAL = "neural"
    AUTO = "auto"


class ResearchProject(BaseModel):
    """Research project containing multiple queries and collections."""
    
    __tablename__ = 'researchproject'
    
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(50), default='active')  # active, archived, completed
    is_public = Column(Boolean, default=False)
    
    # Metadata
    category = Column(String(100))
    keywords = Column(JSON)  # List of keywords
    collaborators = Column(JSON, default=list)  # [{id, name, email, role}]
    timeline = Column(JSON, default=list)  # [{id, title, description, occurred_at, state}]
    deadline = Column(db.DateTime)
    
    # Relationships
    user = relationship('User', back_populates='research_projects')
    queries = relationship('Query', back_populates='project', cascade='all, delete-orphan')
    collections = relationship('Collection', back_populates='project', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'is_public': self.is_public,
            'category': self.category,
            'keywords': self.keywords,
            'collaborators': self.collaborators or [],
            'timeline': self.timeline or [],
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Query(BaseModel):
    """Search query with results and metadata."""
    
    __tablename__ = 'query'
    
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = Column(Integer, ForeignKey('researchproject.id', ondelete='CASCADE'))
    
    # Query details
    query_text = Column(Text, nullable=False)
    query_type = Column(db.Enum(QueryType), default=QueryType.AUTO)
    enhanced_query = Column(Text)  # AI-enhanced version
    
    # Search parameters
    num_results = Column(Integer, default=10)
    search_domain = Column(String(100))
    start_published_date = Column(db.DateTime)
    end_published_date = Column(db.DateTime)
    
    # Results metadata
    total_results = Column(Integer, default=0)
    execution_time = Column(Float)  # Time in seconds
    
    # Status
    is_saved = Column(Boolean, default=False)
    is_scheduled = Column(Boolean, default=False)
    schedule_frequency = Column(String(50))  # daily, weekly, monthly
    
    # Relationships
    user = relationship('User', back_populates='queries')
    project = relationship('ResearchProject', back_populates='queries')
    results = relationship('SearchResult', back_populates='query', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'query_text': self.query_text,
            'query_type': self.query_type.value if self.query_type else None,
            'enhanced_query': self.enhanced_query,
            'num_results': self.num_results,
            'total_results': self.total_results,
            'execution_time': self.execution_time,
            'is_saved': self.is_saved,
            'is_scheduled': self.is_scheduled,
            'project_id': self.project_id,
            'project': self.project.to_dict() if self.project else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SearchResult(BaseModel):
    """Individual search result with content and metadata."""
    
    __tablename__ = 'searchresult'
    
    query_id = Column(Integer, ForeignKey('query.id', ondelete='CASCADE'), nullable=False)
    
    # Result data
    title = Column(String(500), nullable=False)
    url = Column(String(2000), nullable=False)
    snippet = Column(Text)
    full_text = Column(Text)
    
    # Metadata
    author = Column(String(200))
    published_date = Column(db.DateTime)
    domain = Column(String(200))
    language = Column(String(10))
    
    # Analysis
    relevance_score = Column(Float)
    sentiment_score = Column(Float)
    summary = Column(Text)
    key_points = Column(JSON)  # List of key points
    entities = Column(JSON)  # Named entities extracted
    keywords = Column(JSON)  # Extracted keywords
    
    # Citations
    citation_apa = Column(Text)
    citation_mla = Column(Text)
    citation_chicago = Column(Text)
    
    # Status
    is_read = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)
    reading_time = Column(Integer)  # Estimated reading time in minutes
    
    # Relationships
    query = relationship('Query', back_populates='results')
    annotations = relationship('Annotation', back_populates='result', cascade='all, delete-orphan')
    tags = relationship('Tag', secondary=result_tags, back_populates='results')
    collections = relationship('Collection', secondary=collection_results, back_populates='results')
    
    def to_dict(self, include_full_text=False):
        """Convert to dictionary."""
        data = {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'snippet': self.snippet,
            'author': self.author,
            'published_date': self.published_date.isoformat() if self.published_date else None,
            'domain': self.domain,
            'relevance_score': self.relevance_score,
            'sentiment_score': self.sentiment_score,
            'summary': self.summary,
            'key_points': self.key_points,
            'is_read': self.is_read,
            'is_starred': self.is_starred,
            'reading_time': self.reading_time,
        }
        
        if include_full_text:
            data['full_text'] = self.full_text
        
        return data


class Collection(BaseModel):
    """Collection of search results organized by user."""
    
    __tablename__ = 'collection'
    
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = Column(Integer, ForeignKey('researchproject.id', ondelete='CASCADE'))
    
    title = Column(String(200), nullable=False)
    description = Column(Text)
    is_public = Column(Boolean, default=False)
    
    # Relationships
    user = relationship('User', back_populates='collections')
    project = relationship('ResearchProject', back_populates='collections')
    results = relationship('SearchResult', secondary=collection_results, back_populates='collections')
    
    def to_dict(self, include_results: bool = False, include_owner: bool = True):
        """Convert to dictionary."""
        owner_label = None
        if include_owner and self.user:
            parts = [self.user.first_name or '', self.user.last_name or '']
            owner_label = ' '.join(fragment for fragment in parts if fragment).strip()
            if not owner_label:
                owner_label = self.user.username or self.user.email

        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'is_public': self.is_public,
            'result_count': len(self.results),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'project_id': self.project_id,
            'owner': owner_label,
        }

        if include_results:
            data['results'] = [result.to_dict() for result in self.results]

        return data


class Tag(BaseModel):
    """Tags for organizing search results."""
    
    __tablename__ = 'tag'
    
    name = Column(String(50), unique=True, nullable=False, index=True)
    color = Column(String(7), default='#3498db')  # Hex color
    
    # Relationships
    results = relationship('SearchResult', secondary=result_tags, back_populates='tags')
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
        }


class Annotation(BaseModel):
    """User annotations on search results."""
    
    __tablename__ = 'annotation'
    
    result_id = Column(Integer, ForeignKey('searchresult.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    content = Column(Text, nullable=False)
    highlight_text = Column(Text)
    position = Column(JSON)  # Position information for highlighting
    
    # Relationships
    result = relationship('SearchResult', back_populates='annotations')
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'content': self.content,
            'highlight_text': self.highlight_text,
            'position': self.position,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
