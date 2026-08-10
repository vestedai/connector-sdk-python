"""Lazy access to the caller's sealed credential inside a tool call."""

from __future__ import annotations

import json
from collections.abc import Callable

from .credential import CredentialError, CredentialOpener


class CredentialUnavailableError(Exception):
    """No sealed credential was forwarded for this tool call.

    Defensive: when a connector declares a credential schema the platform gates
    dispatch, so a gated tool should never run without one. Reaching this means
    either the connector declares no schema (and the tool should not be asking)
    or the gate is misconfigured — both worth failing loudly rather than
    silently proceeding without an identity.
    """

    code = "credential_unavailable"


class CredentialResolver:
    """Opens the caller's sealed credential once, on first use.

    Lazy because most tools never read the credential, and one that doesn't ask
    should neither pay for an ECDH key agreement nor fail because of one.
    Memoized because a tool may read it more than once.
    """

    def __init__(
        self,
        opener: CredentialOpener | None,
        envelope_json: bytes | None,
        # Lazy: the hub assigns the connector id at HelloAck, after construction.
        connector_id: Callable[[], str],
        user_id: str,
    ) -> None:
        self._opener = opener
        self._envelope_json = envelope_json
        self._connector_id = connector_id
        self._user_id = user_id
        self._opened: dict[str, str] | None = None

    def has_credential(self) -> bool:
        return self._opener is not None and bool(self._envelope_json)

    def credential(self) -> dict[str, str]:
        if self._opened is not None:
            return self._opened

        if not self.has_credential():
            raise CredentialUnavailableError(
                "No user credential was supplied for this tool call. Either this "
                "connector declares no credential schema, or the platform refused "
                "the call before dispatch."
            )

        try:
            envelope = json.loads((self._envelope_json or b"").decode("utf-8"))
        except Exception as exc:
            raise CredentialError(
                "decrypt_failed", "The forwarded credential envelope is malformed."
            ) from exc

        # The AAD identity check happens inside open(). Deliberately not
        # duplicated here: one implementation, on the only path a connector
        # author can reach.
        assert self._opener is not None
        self._opened = self._opener.open(
            envelope, self._connector_id(), self._user_id
        )
        return self._opened
