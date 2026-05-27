"""Public exception hierarchy for the SDK."""

from __future__ import annotations


class ConnectorError(Exception):
    """Base for all SDK errors."""


class TokenError(ConnectorError):
    """JWT verification failed (signature, expiry, revocation)."""


class ToolValidationError(ConnectorError):
    """Tool args failed Pydantic validation."""

    def __init__(self, tool_key: str, message: str) -> None:
        super().__init__(f"{tool_key}: {message}")
        self.tool_key = tool_key
