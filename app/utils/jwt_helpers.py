"""Utility helpers for working with JWT identities."""
import logging
from typing import Optional

from flask_jwt_extended import get_jwt_identity

logger = logging.getLogger(__name__)


def get_current_user_id() -> Optional[int]:
    """Return the authenticated user's ID as an integer if possible."""
    identity = get_jwt_identity()
    if identity is None:
        return None

    try:
        return int(identity)
    except (TypeError, ValueError):
        logger.warning("Invalid JWT identity encountered", extra={"identity": identity})
        return None
