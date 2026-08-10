"""Vested AI Connector SDK — Python.

Public re-exports. Customers import from `vested_connect`, not the submodules.
"""

from pydantic import BaseModel, Field

from .agent import Instruction, agent
from .app import ConnectorApp
from .credential import CredentialError, CredentialOpener
from .credential_handler import (
    CredentialContext,
    CredentialOpDispatcher,
    CredentialValidation,
    UserCredentialHandler,
)
from .credential_resolver import CredentialResolver, CredentialUnavailableError
from .errors import ConnectorError, TokenError, ToolValidationError
from .tool import ToolContext, ToolHandler, tool

__all__ = [
    "ConnectorApp",
    "agent",
    "tool",
    "Instruction",
    "ToolHandler",
    "ToolContext",
    "BaseModel",
    "Field",
    "ConnectorError",
    "TokenError",
    "ToolValidationError",
    "CredentialOpener",
    "CredentialError",
    "CredentialContext",
    "CredentialOpDispatcher",
    "CredentialValidation",
    "UserCredentialHandler",
    "CredentialResolver",
    "CredentialUnavailableError",
]

__version__ = "0.4.0"
