import json
from pathlib import Path
from typing import Any

from vested_connect.credential import CredentialOpener
from vested_connect.credential_handler import (
    CredentialContext,
    CredentialOpDispatcher,
    CredentialValidation,
)
from vested_connect.proto import connector_hub_pb2 as pb

FIXTURE = json.loads(
    (
        Path(__file__).parents[1] / "testdata" / "credential-envelope-vectors.json"
    ).read_text()
)
VECTOR = FIXTURE["vectors"][0]


class SpyHandler:
    def __init__(self, verdict: CredentialValidation | None = None) -> None:
        self.verdict = verdict
        self.saw_credential: dict[str, str] | None = None
        self.saw_ctx: CredentialContext | None = None
        self.revoke_calls = 0

    def validate(
        self, ctx: CredentialContext, credential: dict[str, str]
    ) -> CredentialValidation:
        self.saw_credential = credential
        self.saw_ctx = ctx
        return self.verdict or CredentialValidation.succeeded({"account": "j.smith@erp"})

    def revoke(self, ctx: CredentialContext, credential: dict[str, str]) -> None:
        self.revoke_calls += 1
        self.saw_credential = credential


class ThrowingHandler:
    def validate(
        self, ctx: CredentialContext, credential: dict[str, str]
    ) -> CredentialValidation:
        raise RuntimeError("ERP host db-prod-07.internal refused: connection reset")

    def revoke(self, ctx: CredentialContext, credential: dict[str, str]) -> None:
        pass


def request(user_id: str, op: str = "validate") -> pb.CredentialOpRequest:
    return pb.CredentialOpRequest(
        op_id="op-1",
        op=op,
        user_id=user_id,
        user_email="j.smith@example.com",
        envelope_json=json.dumps(VECTOR["envelope"]).encode(),
        deadline_ms=5000,
    )


def dispatcher(handler: Any) -> CredentialOpDispatcher:
    return CredentialOpDispatcher(
        CredentialOpener(FIXTURE["connector_private_key_pkcs8_pem"]),
        handler,
        VECTOR["connector_id"],
    )


def test_opens_the_envelope_and_hands_the_handler_plaintext() -> None:
    handler = SpyHandler()
    resp = dispatcher(handler).dispatch(request(VECTOR["user_id"]))

    assert resp.ok is True
    assert handler.saw_credential == VECTOR["plaintext"]
    assert handler.saw_ctx is not None and handler.saw_ctx.user_id == VECTOR["user_id"]
    assert resp.display["account"] == "j.smith@erp"


def test_surfaces_a_handler_refusal() -> None:
    resp = dispatcher(
        SpyHandler(CredentialValidation.failed("ERP rejected those credentials."))
    ).dispatch(request(VECTOR["user_id"]))

    assert resp.ok is False
    assert resp.error == "ERP rejected those credentials."


def test_refuses_envelope_for_a_different_user_without_calling_the_handler() -> None:
    handler = SpyHandler()
    resp = dispatcher(handler).dispatch(request("999999"))

    assert resp.ok is False
    assert handler.saw_credential is None


def test_never_leaks_handler_exception_text() -> None:
    resp = dispatcher(ThrowingHandler()).dispatch(request(VECTOR["user_id"]))

    assert resp.ok is False
    assert "db-prod-07.internal" not in resp.error


def test_runs_revoke_when_asked() -> None:
    handler = SpyHandler()
    resp = dispatcher(handler).dispatch(request(VECTOR["user_id"], "revoke"))

    assert resp.ok is True
    assert handler.revoke_calls == 1


def test_answers_rather_than_staying_silent_without_a_handler() -> None:
    resp = dispatcher(None).dispatch(request(VECTOR["user_id"]))

    assert resp.ok is False
    assert resp.op_id == "op-1"
