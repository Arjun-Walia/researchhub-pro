"""Custom exceptions for ResearchHub Pro."""


class ResearchHubException(Exception):
    """Base exception for ResearchHub."""
    pass


class ValidationError(ResearchHubException):
    """Validation error."""
    pass


class AuthenticationError(ResearchHubException):
    """Authentication failed."""
    pass


class AuthorizationError(ResearchHubException):
    """Authorization failed - insufficient permissions."""
    pass


class ResourceNotFoundError(ResearchHubException):
    """Requested resource not found."""
    pass


class RateLimitError(ResearchHubException):
    """Rate limit exceeded."""
    pass


class ExternalAPIError(ResearchHubException):
    """External API call failed."""
    pass


class DatabaseError(ResearchHubException):
    """Database operation failed."""
    pass


class CacheError(ResearchHubException):
    """Cache operation failed."""
    pass


class ExportError(ResearchHubException):
    """Export operation failed."""
    pass


class QuotaExceededError(ResearchHubException):
    """User quota exceeded."""
    pass
