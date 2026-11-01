"""Domain errors. The API layer maps these to HTTP status codes."""
from __future__ import annotations


class DomainError(Exception):
    status_code = 400
    code = "DOMAIN_ERROR"

    def __init__(self, message: str, details=None):
        super().__init__(message)
        self.message = message
        self.details = details or []


class NotFoundError(DomainError):
    status_code = 404
    code = "NOT_FOUND"


class ValidationFailed(DomainError):
    status_code = 422
    code = "VALIDATION_FAILED"


class ForbiddenError(DomainError):
    status_code = 403
    code = "FORBIDDEN"


class ConflictError(DomainError):
    status_code = 409
    code = "CONFLICT"


class UnauthorizedError(DomainError):
    status_code = 401
    code = "UNAUTHORIZED"
