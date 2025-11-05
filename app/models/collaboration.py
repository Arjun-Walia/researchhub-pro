"""Collaboration models for team features."""
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum

from .base import BaseModel, db


class TeamRole(enum.Enum):
    """Team member roles."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Team(BaseModel):
    """Team for collaborative research."""
    
    __tablename__ = 'team'
    
    name = Column(String(200), nullable=False)
    description = Column(db.Text)
    is_active = Column(Boolean, default=True)
    
    # Settings
    max_members = Column(Integer, default=10)
    is_public = Column(Boolean, default=False)
    
    # Relationships
    members = relationship('TeamMember', back_populates='team', cascade='all, delete-orphan')
    shared_resources = relationship('SharedResource', back_populates='team', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'member_count': len(self.members),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TeamMember(BaseModel):
    """Team membership with roles."""
    
    __tablename__ = 'teammember'
    
    team_id = Column(Integer, ForeignKey('team.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    role = Column(Enum(TeamRole), default=TeamRole.MEMBER, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    team = relationship('Team', back_populates='members')
    user = relationship('User', back_populates='team_memberships')
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'team_id': self.team_id,
            'user_id': self.user_id,
            'role': self.role.value,
            'is_active': self.is_active,
            'joined_at': self.created_at.isoformat() if self.created_at else None,
        }


class SharedResource(BaseModel):
    """Shared research resources within a team."""
    
    __tablename__ = 'sharedresource'
    
    team_id = Column(Integer, ForeignKey('team.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    resource_type = Column(String(50), nullable=False)  # project, collection, query
    resource_id = Column(Integer, nullable=False)
    
    # Permissions
    can_edit = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    
    # Relationships
    team = relationship('Team', back_populates='shared_resources')
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'can_edit': self.can_edit,
            'can_delete': self.can_delete,
            'shared_at': self.created_at.isoformat() if self.created_at else None,
        }
