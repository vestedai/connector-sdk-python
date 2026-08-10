# Per-user credentials

Some integrations act on behalf of the person asking, not on behalf of the
connector. An ERP that enforces its own permissions is the clearest case: if
every call arrives as one service account, the ERP's ACLs do nothing and its
audit log names a robot instead of a human.

Per-user credentials fix that. Each user stores their own credentials for your
integration; the platform hands them to your worker on every tool call.

**The platform cannot read them.** Credentials are sealed in the user's browser
with a public key generated for your connector. The private half lives only on
your worker. A full database dump of the platform leaks nothing.

---

## Opting in

A connector declares a credential schema at registration. Declaring one is what
turns the whole feature on for your integration — a connector that declares
nothing is unaffected in every respect.

```python
from vested_connect import CredentialContext, CredentialValidation


class ErpCredentials:
    def __init__(self, erp: ErpClient) -> None:
        self._erp = erp

    def validate(
        self, ctx: CredentialContext, credential: dict[str, str]
    ) -> CredentialValidation:
        who = self._erp.whoami(credential["username"], credential["password"])

        if who is None:
            return CredentialValidation.failed("ERP rejected those credentials.")
        return CredentialValidation.succeeded({"account": who.login, "role": who.role})

    def revoke(self, ctx: CredentialContext, credential: dict[str, str]) -> None:
        """Optional: tear down a remote session. Best-effort."""
```
Register it, with the private key that opens sealed envelopes:

Register the handler on your `ConnectorApp` alongside your agents and tools.

Keys come from `VESTED_CREDENTIAL_PRIVATE_KEY` (or `VESTED_CREDENTIAL_PRIVATE_KEY_FILE`)
when you don't pass them explicitly. Registering a handler without a key throws
at startup rather than failing every credential check later with a puzzling
message.

## Using them in a tool

```python
def handle(self, args: Args, ctx: ToolContext) -> dict:
    creds = ctx.credential()          # {"username": "…", "password": "…"}

    return self._erp.search_as_user(creds["username"], creds["password"], args.q)
```

`credential()` is lazy and memoized: a tool that never calls it never pays for a
decrypt, and calling it twice costs one key agreement.

Use `ctx.has_credential()` if a tool works with or without one.

## What the SDK guarantees

**An envelope sealed for another user throws.** Every envelope is
cryptographically bound to the connector and the user it was sealed for, and
the SDK verifies that binding before handing you plaintext. You cannot
accidentally serve user A's request with user B's credentials — the check is
inside `credential()`, not something you remember to call.

**A tool call without a usable credential never reaches you.** The platform
refuses it and tells the user what to do. By the time your handler runs, the
credential is present and valid.

## The declaration

Field types are `text`, `password`, `url`, `select`. A `password` field renders
masked; `select` needs `options`. The platform builds the user's form from this
— you never write UI.

Declare `kind`, `title` and one entry per field on your handler, using this SDK's declaration style (the same mechanism your agents and tools already use).

## Key rotation

An operator can rotate your connector's keypair. Envelopes sealed under the old
key stop being readable, so affected users are asked to re-enter.

To ride out the overlap, keep both keys in the ring — newest first, separated by
a blank line in `VESTED_CREDENTIAL_PRIVATE_KEY`. The SDK tries each in turn.

## Things worth knowing

- **`display` is shown to the user.** Put an account name or role in it, never
  the credential.
- **Error text from `failed()` is shown verbatim.** Don't include stack traces
  or internal hostnames.
- **Automated runs need an owner.** A scheduled workflow uses the credentials of
  the person who owns it. A workflow instance with no owner at all is refused
  rather than run as an arbitrary employee.
