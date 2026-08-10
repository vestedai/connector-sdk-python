import json
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from vested_connect.credential import CredentialError, CredentialOpener

FIXTURE = json.loads(
    (
        Path(__file__).parents[2] / "testdata" / "credential-envelope-vectors.json"
    ).read_text()
)


def opener() -> CredentialOpener:
    return CredentialOpener(FIXTURE["connector_private_key_pkcs8_pem"])


def negative(name: str) -> dict[str, Any]:
    return next(n for n in FIXTURE["negative"] if n["name"] == name)


def fresh_key_pem() -> str:
    return (
        ec.generate_private_key(ec.SECP256R1())
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode()
    )


def test_opens_every_positive_vector() -> None:
    for v in FIXTURE["vectors"]:
        assert (
            opener().open(v["envelope"], v["connector_id"], v["user_id"])
            == v["plaintext"]
        ), v["name"]


def test_rejects_envelope_sealed_for_a_different_user() -> None:
    n = negative("aad_identity_mismatch")
    with pytest.raises(CredentialError) as exc:
        opener().open(n["envelope"], n["open_as_connector_id"], n["open_as_user_id"])
    assert exc.value.code == "identity_mismatch"


def test_rejects_tampered_ciphertext() -> None:
    n = negative("tampered_ciphertext")
    with pytest.raises(CredentialError) as exc:
        opener().open(n["envelope"], n["open_as_connector_id"], n["open_as_user_id"])
    assert exc.value.code == "decrypt_failed"


def test_rejects_unknown_algorithm() -> None:
    n = negative("unknown_algorithm")
    with pytest.raises(CredentialError) as exc:
        opener().open(n["envelope"], n["open_as_connector_id"], n["open_as_user_id"])
    assert exc.value.code == "unsupported_alg"


def test_keyring_tries_every_key() -> None:
    ring = CredentialOpener(fresh_key_pem(), FIXTURE["connector_private_key_pkcs8_pem"])
    v = FIXTURE["vectors"][0]
    assert ring.open(v["envelope"], v["connector_id"], v["user_id"]) == v["plaintext"]


def test_fails_when_no_key_in_the_ring_opens_the_envelope() -> None:
    v = FIXTURE["vectors"][0]
    with pytest.raises(CredentialError) as exc:
        CredentialOpener(fresh_key_pem()).open(
            v["envelope"], v["connector_id"], v["user_id"]
        )
    assert exc.value.code == "decrypt_failed"
