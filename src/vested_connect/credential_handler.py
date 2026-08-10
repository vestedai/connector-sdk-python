"""Worker-side handling of credential lifecycle operations.

The platform cannot open a sealed credential — only this worker can — so every
question about whether a user's credentials work is answered here.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Protocol

from google.protobuf.struct_pb2 import Struct

from .credential import CredentialError, CredentialOpener
from .proto import connector_hub_pb2 as pb

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CredentialContext:
    """Identity context for a credential lifecycle operation.

    Deliberately carries no agent or tool key — a credential op is not scoped to
    a tool — and no raw envelope: the SDK opens it and hands the handler
    plaintext, so connector authors cannot skip the identity check that makes
    per-user auth mean anything.
    """

    op_id: str
    user_id: str
    user_email: str
    employee_no: str = ""
    erp_identifier: str = ""


@dataclass(frozen=True)
class CredentialValidation:
    """A handler's verdict.

    ``display`` is shown to the user, so it must contain only non-secret facts —
    an account name or role, never the credential itself.
    """

    ok: bool
    error: str = ""
    display: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def succeeded(display: dict[str, str] | None = None) -> CredentialValidation:
        return CredentialValidation(ok=True, display=display or {})

    @staticmethod
    def failed(user_facing_message: str) -> CredentialValidation:
        """user_facing_message is shown verbatim. Do not include the
        credential, a stack trace, or internal hostnames."""
        return CredentialValidation(ok=False, error=user_facing_message)


class UserCredentialHandler(Protocol):
    """Implemented by a connector that wants per-user credentials.

    ``credential`` arrives already decrypted and already verified as belonging
    to the calling user.
    """

    def validate(
        self, ctx: CredentialContext, credential: dict[str, str]
    ) -> CredentialValidation: ...

    def revoke(self, ctx: CredentialContext, credential: dict[str, str]) -> None:
        """Best-effort: the platform deletes its copy regardless."""
        ...


class CredentialOpDispatcher:
    """Never raises and always answers.

    Silence would make the platform wait out its full deadline for an op that
    was never going to complete.
    """

    def __init__(
        self,
        opener: CredentialOpener,
        handler: UserCredentialHandler | None,
        connector_id: str,
    ) -> None:
        self._opener = opener
        self._handler = handler
        self._connector_id = connector_id

    def dispatch(self, req: pb.CredentialOpRequest) -> pb.CredentialOpResponse:
        resp = pb.CredentialOpResponse(op_id=req.op_id, ok=False)

        if self._handler is None:
            resp.error = "This integration does not accept per-user credentials."
            return resp

        try:
            envelope = json.loads(req.envelope_json.decode("utf-8"))
        except Exception:
            resp.error = "The stored credential is unreadable. Please enter it again."
            return resp

        try:
            credential = self._opener.open(envelope, self._connector_id, req.user_id)
        except CredentialError as e:
            # The message can name key fingerprints and internals, so it is
            # logged but never returned. An identity mismatch is a security
            # event, not a user-fixable typo.
            _log.warning(
                "credential envelope could not be opened (op=%s user=%s): %s",
                req.op_id,
                req.user_id,
                e.code,
            )
            resp.error = (
                "The stored credential could not be read by this integration. "
                "Please enter it again."
            )
            return resp

        ctx = CredentialContext(
            op_id=req.op_id,
            user_id=req.user_id,
            user_email=req.user_email,
            employee_no=req.employee_no,
            erp_identifier=req.erp_identifier,
        )

        try:
            if req.op == "revoke":
                self._handler.revoke(ctx, credential)
                resp.ok = True
                return resp

            verdict = self._handler.validate(ctx, credential)
            resp.ok = verdict.ok
            resp.error = verdict.error
            if verdict.display:
                struct = Struct()
                for key, value in verdict.display.items():
                    struct[str(key)] = str(value)
                resp.display.CopyFrom(struct)
        except Exception:
            _log.exception("credential handler raised (op=%s)", req.op_id)
            resp.ok = False
            resp.error = "The integration could not check these credentials right now."

        return resp
