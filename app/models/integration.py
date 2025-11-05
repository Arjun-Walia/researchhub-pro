"""Models related to external integrations and OAuth connections."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship

from .base import BaseModel, db


class IntegrationEvent(BaseModel):
    """Audit log for API integration activity."""

    __tablename__ = "integration_events"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False, index=True)
    action = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False)
    message = Column(String(255), nullable=False)
    details = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="integration_events")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "action": self.action,
            "status": self.status,
            "message": self.message,
            "metadata": self.details or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def record(
        cls,
        user_id: int,
        provider: str,
        action: str,
        status: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "IntegrationEvent":
        event = cls(
            user_id=user_id,
            provider=provider,
            action=action,
            status=status,
            message=message,
            details=metadata or {},
        )
        db.session.add(event)
        db.session.commit()
        return event


class OAuthConnection(BaseModel):
    """Represents an OAuth provider connection for a user."""

    __tablename__ = "oauth_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_oauth_provider_per_user"),
    )

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False, index=True)
    status = Column(String(20), default="disconnected", nullable=False)
    label = Column(String(120), nullable=True)
    connected_at = Column(DateTime, nullable=True)
    disconnected_at = Column(DateTime, nullable=True)
    external_id = Column(String(191), nullable=True)
    details = Column("metadata", JSON, nullable=True)
    last_error = Column(Text, nullable=True)
    requires_reauth = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="oauth_connections")

    def mark_connected(self, external_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        self.status = "connected"
        self.connected_at = datetime.utcnow()
        self.disconnected_at = None
        self.external_id = external_id
        self.details = metadata or {}
        self.last_error = None
        self.requires_reauth = False

    def mark_disconnected(self, reason: Optional[str] = None):
        self.status = "disconnected"
        self.disconnected_at = datetime.utcnow()
        if reason:
            self.last_error = reason
        self.requires_reauth = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "label": self.label or self.provider.title(),
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "disconnected_at": self.disconnected_at.isoformat() if self.disconnected_at else None,
            "requires_reauth": self.requires_reauth,
            "metadata": self.details or {},
            "last_error": self.last_error,
        }
