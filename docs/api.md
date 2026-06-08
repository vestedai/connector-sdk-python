# API Reference

## ConnectorApp

The top-level facade. Build one in `bootstrap.py`; the CLI loads and runs it.

Source: `src/vested_connect/app.py`

**`ConnectorApp.create() -> ConnectorApp`**
Static constructor. All configuration follows via chained calls.

```python
app = ConnectorApp.create()
```

**`.with_logger(logger: logging.Logger) -> ConnectorApp`**
Plug in any `logging.Logger`. The SDK binds per-call fields (`invocation_id`, `agent_key`, `tool_key`) to a `LoggerAdapter` before passing it to each handler. Default: `logging.getLogger("vested_connect")`.

```python
import logging
app.with_logger(logging.getLogger("myapp.connector"))
```

**`.scan_module(module: str | types.ModuleType) -> ConnectorApp`**
Discover `@agent`- and `@tool`-decorated classes in the given module. The module must already be imported (or importable by dotted name) before `run()` is called.

```python
app.scan_module("myapp.agents").scan_module("myapp.tools")
```

**`.agents -> list[AgentDecl]`**
Read-only list of all declared agents after `scan_module()` has run.

**`.tools -> list[ToolDecl]`**
Read-only list of all declared tools after `scan_module()` has run.

**`.run(token: str, hub: str, insecure: bool = False) -> int`**
Run the asyncio supervisor loop. Connects to the hub, sends Hello+Register, then enters steady-state. On disconnect, backs off and reconnects. Returns `0` on clean shutdown (SIGTERM/SIGINT), `78` on token rejection (`EX_CONFIG`). `insecure=True` uses plaintext gRPC — for local dev only.

```python
import asyncio, os
asyncio.run(app.run(token=os.environ["VESTED_CONNECTOR_TOKEN"],
                    hub=os.environ["VESTED_CONNECTOR_HUB"]))
```

The CLI wraps this with `asyncio.run()`. In your own entry point you may call `run()` directly inside an async context.

---

## `@agent` decorator

Declare an agent. Applied to a class — the class body is unused; it is a declaration container only.

```python
from vested_connect import agent, Instruction

@agent(
    key="myns.orders",
    name="Orders",
    description="Manages order data",      # optional
    status="active",                        # default
    model_provider="openai",               # optional; default provider if set
    model_name="gpt-4o",                   # optional
    model_config={"temperature": 0.2},     # optional
    instructions=[
        Instruction(type="system",  position=0, body="You manage order data."),
        Instruction(type="persona", position=1, body="Professional, concise."),
    ],
)
class OrdersAgent: ...
```

`key` and `name` are required. All other fields are optional.

### `Instruction` dataclass

```python
@dataclass
class Instruction:
    type: str       # "system" | "task" | "persona" | "safety"
    position: int   # ascending sort order
    body: str       # prompt text
    format: str = "markdown"  # "markdown" | "jinja" | "plain"
```

---

## `@tool` decorator

Declare a tool and bind it to a handler class. The class must subclass `ToolHandler`.

```python
from vested_connect import tool, ToolHandler, ToolContext, BaseModel, Field

@tool(
    agent_key="myns.orders",
    key="myns.orders.get",
    name="Get order",
    description="Returns a single order by ID.",
    sensitivity="read",        # optional; see allowed values below
    deadline_ms=5000,          # optional; default 30 000
    max_result_bytes=65536,    # optional; default 1 MiB
)
class GetOrder(ToolHandler):
    class Args(BaseModel):
        id: str = Field(description="Order ID")

    async def handle(self, args: Args, ctx: ToolContext) -> dict:
        return {"status": "shipped"}
```

The input JSON Schema is auto-generated from the inner `Args` Pydantic model using `Args.model_json_schema()`. If you need fine-grained control, pass `input_schema: dict` to `@tool` instead of defining `Args`.

### `sensitivity` parameter

The optional `sensitivity` keyword lets the connector declare the risk level of a tool. The hub stores this alongside the tool and exposes it in the admin UI; admins can later override it without redeploying the connector.

| Value | Meaning |
|---|---|
| `"read"` | Read-only; no side-effects. |
| `"write"` | Creates or updates data. |
| `"destructive"` | Deletes or irreversibly modifies data. |
| `"external_call"` | Makes a call to an external system (e.g. payment, email, webhook). |
| `"medium"` | Catch-all moderate-risk bucket. |

Omitting `sensitivity` (or passing `""`) leaves the field unset; the hub will default it to `external_call`. Passing any value outside the allowed set raises `ValueError` at decoration time — not at runtime.

Output schema is inferred from the return type annotation if it is a Pydantic model subclass; otherwise pass `output_schema: dict` explicitly.

---

## `ToolHandler` base class

Source: `src/vested_connect/tool.py`

```python
class ToolHandler:
    async def handle(self, args: BaseModel, ctx: ToolContext) -> dict | BaseModel:
        raise NotImplementedError
```

`args` — Pydantic model instance, already validated against the tool's input schema.
Return value — dict or Pydantic model; validated against the output schema before reaching the LLM.

Raise any exception to signal a handler error. The hub converts it to a `ToolCallResponse{error: ...}` and surfaces it in the run timeline.

---

## `ToolContext` dataclass

Source: `src/vested_connect/tool.py`

Read-only value object passed to every handler.

| Field | Type | Description |
|---|---|---|
| `invocation_id` | `str` | Hub-minted UUIDv7. Stable across logs and traces. |
| `organization_id` | `str` | Org that owns this run. |
| `user_id` | `str` | User who triggered the run. Empty for system/scheduled runs. |
| `user_email` | `str` | Caller's email. Empty for system runs. **PII — do not log or persist.** |
| `conversation_id` | `str` | Conversation this run belongs to. |
| `agent_key` | `str` | Key of the agent being run. |
| `tool_key` | `str` | Key of this tool. |
| `deadline_ms` | `int` | Remaining deadline in ms. Handler should respect this. |
| `logger` | `logging.LoggerAdapter` | Pre-bound with `invocation_id`, `agent_key`, `tool_key`. |
| `invoked_at` | `datetime` | Wall-clock time the hub dispatched the call (UTC). |
| `employee_no` | `str` | Nullable. The calling user's HR/ERP employee number. Empty string when unset. Source: `ToolCallRequest.employee_no` (proto field 10). |
| `erp_identifier` | `str` | Nullable. The calling user's ERP system identifier (e.g. SAP user ID). Empty string when unset. Source: `ToolCallRequest.erp_identifier` (proto field 11). |
| `erp_department_identifiers` | `tuple[str, ...]` | Nullable. ERP identifiers of every department the calling user belongs to within the run's org. Empty tuple when the user has no departments or none carry an ERP id. Source: `ToolCallRequest.erp_department_identifiers` (proto field 12). |

Helpers:

```python
ctx.caller_email_or_none()  # returns None for system runs
ctx.is_system_run()         # True when user_id == ""
```

---

## Re-exports from Pydantic

`BaseModel` and `Field` are re-exported from `vested_connect` for convenience. Using them is optional — you may import directly from `pydantic` instead.

```python
from vested_connect import BaseModel, Field
# equivalent to:
from pydantic import BaseModel, Field
```

---

## Error types

Source: `src/vested_connect/errors.py`

| Class | Raised when |
|---|---|
| `ConnectorError` | Base class for all SDK errors. |
| `TokenError` | Token rejected by the hub (`GoAway{token_rotated}` or `GoAway{revoked}`). Causes exit 78. |
| `ToolValidationError` | Input or output schema validation failed at the connector side. |

---

## `vested-connect` CLI

Installed as a console script by the package. Also invocable as `python -m vested_connect.cli`.

**`vested-connect worker`**

Run a connector worker.

| Flag | Default | Description |
|---|---|---|
| `--bootstrap=PATH` | required | Path to the Python bootstrap file. The file is imported; all `@agent`/`@tool` decorators must run at import time. |
| `--hub=HOST:PORT` | `$VESTED_CONNECTOR_HUB` | Hub address. |
| `--token=TOKEN` | `$VESTED_CONNECTOR_TOKEN` | Connector JWT. |
| `--token-stdin` | — | Read the token from stdin instead of the flag or env var. |
| `--insecure` | — | Use plaintext gRPC (no TLS). Local dev only. |
| `--workers=N` | `4` | Asyncio semaphore size for concurrent tool calls. |

```bash
vested-connect worker --bootstrap=./bootstrap.py
```

## Next

[Operations](operations.md)
