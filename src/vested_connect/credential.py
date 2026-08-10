"""Sealed user-credential envelopes.

The core seals with the connector's public key and cannot open what it stored;
this module is the only place the plaintext exists inside a worker.

Format: ECDH-P256 -> HKDF-SHA256 -> AES-256-GCM. See
docs/superpowers/specs/2026-08-10-connector-user-auth-design.md.
"""

from __future__ import annotations

import base64
import hmac
import json
from typing import Any, Literal

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

CREDENTIAL_ALG = "ECDH-P256+HKDF-SHA256+A256GCM"

_INFO = b"vested-connector-credential-v1"
_SALT = bytes(32)
_TAG_BYTES = 16

CredentialErrorCode = Literal["identity_mismatch", "decrypt_failed", "unsupported_alg"]


class CredentialError(Exception):
    """Raised when an envelope cannot be opened, or is not ours to open."""

    def __init__(self, code: CredentialErrorCode, message: str) -> None:
        super().__init__(message)
        self.code: CredentialErrorCode = code


class CredentialOpener:
    """Opens sealed credential envelopes using a keyring of private keys."""

    def __init__(self, *private_key_pems: str) -> None:
        """private_key_pems: PKCS#8 PEM private keys, newest first."""
        self._keyring = list(private_key_pems)

    def open(
        self, envelope: dict[str, Any], connector_id: str, user_id: str
    ) -> dict[str, str]:
        alg = envelope.get("alg", "")
        if alg != CREDENTIAL_ALG:
            raise CredentialError(
                "unsupported_alg", f"unsupported credential envelope algorithm {alg!r}"
            )

        # Verify the binding BEFORE decrypting. GCM enforces the AAD anyway, but
        # checking here turns a generic decrypt failure into a specific,
        # alertable security signal: an envelope sealed for one identity
        # arrived on a call made by another.
        expected = f"connector:{connector_id}|user:{user_id}|v{envelope.get('v', 1)}"
        actual = envelope.get("aad", "")
        if not hmac.compare_digest(expected, actual):
            raise CredentialError(
                "identity_mismatch",
                f"credential envelope identity mismatch: envelope is bound to {actual!r}, "
                f"invocation is {expected!r}",
            )

        try:
            ephemeral = serialization.load_der_public_key(
                base64.b64decode(envelope["epk"])
            )
            iv = base64.b64decode(envelope["iv"])
            raw = base64.b64decode(envelope["ct"])
        except Exception as exc:  # malformed base64 / DER
            raise CredentialError(
                "decrypt_failed", "credential envelope is malformed"
            ) from exc

        if not isinstance(ephemeral, ec.EllipticCurvePublicKey):
            raise CredentialError(
                "decrypt_failed", "ephemeral key is not an EC public key"
            )

        if len(raw) <= _TAG_BYTES:
            raise CredentialError(
                "decrypt_failed", "credential envelope ciphertext is too short"
            )

        for pem in self._keyring:
            try:
                private = serialization.load_pem_private_key(pem.encode(), password=None)
                if not isinstance(private, ec.EllipticCurvePrivateKey):
                    continue
                z = private.exchange(ec.ECDH(), ephemeral)
                key = HKDF(
                    algorithm=hashes.SHA256(), length=32, salt=_SALT, info=_INFO
                ).derive(z)
                plaintext = AESGCM(key).decrypt(iv, raw, actual.encode())
            except Exception:
                continue  # wrong key in the ring, or authentication failed

            decoded = json.loads(plaintext)
            if not isinstance(decoded, dict):
                raise CredentialError(
                    "decrypt_failed", "credential payload is not an object"
                )
            return decoded

        raise CredentialError(
            "decrypt_failed",
            "credential envelope failed to decrypt or authenticate under any key in the ring",
        )
