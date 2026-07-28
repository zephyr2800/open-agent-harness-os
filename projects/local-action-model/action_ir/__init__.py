"""Versioned protocol primitives for the Open Local Action Model."""

from .validation import ActionValidationError, validate_decision

__all__ = ["ActionValidationError", "validate_decision"]
