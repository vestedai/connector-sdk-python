import json
from pathlib import Path

import pytest

from vested_connect.credential import CredentialError, CredentialOpener
from vested_connect.credential_resolver import (
    CredentialResolver,
    CredentialUnavailableError,
)

FIXTURE = json.loads(
    (
        Path(__file__).parents[1] / "testdata" / "credential-envelope-vectors.json"
    ).read_text()
)
VECTOR = FIXTURE["vectors"][0]


def resolver_for(connector_id: str, user_id: str) -> CredentialResolver:
    return CredentialResolver(
        CredentialOpener(FIXTURE["connector_private_key_pkcs8_pem"]),
        json.dumps(VECTOR["envelope"]).encode(),
        lambda: connector_id,
        user_id,
    )


def test_hands_a_tool_the_decrypted_credential() -> None:
    r = resolver_for(VECTOR["connector_id"], VECTOR["user_id"])

    assert r.has_credential() is True
    assert r.credential() == VECTOR["plaintext"]


def test_memoizes_so_two_reads_cost_one_key_agreement() -> None:
    r = resolver_for(VECTOR["connector_id"], VECTOR["user_id"])

    assert r.credential() is r.credential()


def test_refuses_an_envelope_sealed_for_a_different_user() -> None:
    # The check lives in CredentialOpener, on the only path a tool author can
    # reach — a tool cannot opt out of it.
    r = resolver_for(VECTOR["connector_id"], "999999")

    with pytest.raises(CredentialError):
        r.credential()


def test_reports_no_credential_rather_than_raising() -> None:
    r = CredentialResolver(None, None, lambda: "42", "1337")

    assert r.has_credential() is False


def test_raises_named_error_when_asked_for_one_never_sent() -> None:
    r = CredentialResolver(None, None, lambda: "42", "1337")

    with pytest.raises(CredentialUnavailableError):
        r.credential()


def test_resolves_the_connector_id_lazily() -> None:
    box = {"id": ""}
    r = CredentialResolver(
        CredentialOpener(FIXTURE["connector_private_key_pkcs8_pem"]),
        json.dumps(VECTOR["envelope"]).encode(),
        lambda: box["id"],
        VECTOR["user_id"],
    )

    # Constructed before the handshake; the id lands afterwards.
    box["id"] = VECTOR["connector_id"]

    assert r.credential() == VECTOR["plaintext"]
