# Upgrading

> **Other language SDKs:** the connector SDK also ships for [PHP](https://packagist.org/packages/vested-ai/connector-sdk-php) (`vested-ai/connector-sdk-php`), [Node.js](https://www.npmjs.com/package/@vested-ai/connector-sdk) (`@vested-ai/connector-sdk`), and [C# / .NET](https://www.nuget.org/packages/VestedAI.ConnectorSdk) (`VestedAI.ConnectorSdk`) — all at wire parity, including connector-declared tool sensitivity. See the [SDK index](../../README.md).

## Coming from the PHP SDK

This section maps PHP SDK concepts to their Python equivalents for customers evaluating or migrating between the two SDKs.

### Install

| PHP | Python |
|---|---|
| `composer require vested-ai/connector-sdk-php` | `pip install vested-connect-sdk` |
| `vendor/bin/vested-connect worker --bootstrap=./bootstrap.php` | `vested-connect worker --bootstrap=./bootstrap.py` |

### Declaring Agents

| PHP | Python |
|---|---|
| `#[Agent(key: '...')]` PHP attribute on a class | `@agent(key="...")` decorator on a class |
| `ConnectorApp::create()->agent('key')->withModel(...)->endAgent()` | `@agent(key="...", model_provider="...", model_name="...")` |
| `AgentBuilder` fluent interface | `@agent(...)` decorator parameters |
| `#[Instruction(type: 'system', position: 0, body: '...')]` | `Instruction(type="system", position=0, body="...")` passed to `@agent(instructions=[...])` |

### Declaring Tools

| PHP | Python |
|---|---|
| `#[Tool(agentKey: '...', inputSchema: [...])]` on class implementing `ToolHandler` | `@tool(agent_key="...", ...)` on class extending `ToolHandler` |
| `inputSchema: ['type' => 'object', ...]` — hand-written JSON Schema array | `class Args(BaseModel): id: str` — Pydantic model, schema auto-generated |
| `public function handle(array $args, ToolContext $ctx): array` | `async def handle(self, args: Args, ctx: ToolContext) -> dict` |
| Synchronous handler | `async def` handler (asyncio) |

### Bootstrap File

| PHP | Python |
|---|---|
| `bootstrap.php` returns a `ConnectorApp` instance | `bootstrap.py` imports modules that register decorators; `ConnectorApp.create().scan_module(...)` |
| `ConnectorApp::create()->scanNamespace('MyApp\\Tools', __DIR__.'/src/Tools')->build()` | `ConnectorApp.create().scan_module("myapp.tools")` |
| PSR-11 container for dependency injection | Constructor injection via `__init__`; async session objects created in `handle()` or class-level async factories |

### Concurrency Model

| PHP | Python |
|---|---|
| Swoole coroutines | asyncio (single event loop, `async def` handlers) |
| `ext-swoole` required | No C extension required; pure Python with `grpcio` |
| `Coroutine::defer` for resource cleanup | `async with` / `asyncio.to_thread()` |
| `$pool = new MyPdoPool(size: 8)` | `asyncpg.create_pool(min_size=4, max_size=8)` |

### Env Vars and CLI

Env var names are identical (`VESTED_CONNECTOR_TOKEN`, `VESTED_CONNECTOR_HUB`). Exit codes are identical (0/78). Reconnect backoff schedule is identical (1 s → 30 s cap, ±20% jitter).

### Items Exclusive to the PHP SDK (not applicable to Python)

The following are PHP-specific implementation details. They are documented here only for cross-SDK reference and appear nowhere else in the Python docs:

- `ext-swoole`, `Swoole\Coroutine::defer`, `PDOProxy` — PHP/Swoole runtime.
- `bootstrap.php` — PHP entry point filename convention.
- `composer require` / Packagist — PHP package manager.
- Monolog loop-detection workaround — PHP-specific logging issue.
- `Vested\Connect\Sdk\HubClient` / `ParentProcess` namespaces — removed PHP internals.

---

## v0.6.0 Release Notes

### v0.6.0 — a tool can declare the agents it binds to

Tools bind to agents by namespace today: `myns.orders.get` belongs to agent `myns.orders` and nowhere else. Sharing behaviour across agents therefore meant duplicating the handler — a second class in a second namespace wrapping the same logic.

A tool can now name the agents it binds to. ```python
@tool(key="erp.data.run_sql", description="…",
      agents=["erp.data", "erp.retail"])
```

`agents` is a keyword-only parameter with a default, so existing `@tool(...)` call sites are unaffected.

**Omitting it changes nothing.** A connector that never sets it binds exactly the tools it binds today.

**A present list is authoritative, not additive.** The key's namespace confers nothing once a list is present, so a tool may live in one namespace and be callable only from another. ``"*"`` means every agent this connector declares and cannot be combined with explicit keys.

Refused before the worker dials the hub: an agent key this connector does not declare, ``"*"`` mixed with explicit keys, and a tool that neither matches an agent namespace nor names any agent. Declaring a list that omits the agent named in the tool's own key is legal — it is how you say "lives here, callable from there" — and logs a startup warning.

### v0.6.0 — the baseline fingerprint now covers agent→tool binding

**Behavioural, not source-breaking. Every connector re-registers once.**

`baseline_fingerprint` did not cover which agents a tool was bound to. That was safe only while binding was *derived* from the tool key — you could not change one without changing the other. With an explicit binding field, re-pointing a tool at different agents would have produced an identical fingerprint, and the hub would have short-circuited the registration as unchanged. Nothing would error; the change simply would not happen.

Each agent's canonical entry now carries its bound tool keys, so your connector's fingerprint changes once on upgrade even if you never use the new field. The re-registration produces **no draft** for review unless an agent's actual tool set changed.

### v0.6.0 — two cross-SDK fingerprint divergences fixed

Found while adding the above, and fixed in the same release. .NET, Node and Python canonicalise the same structure and are meant to agree; nothing checked that they did.

- **Sort comparer.** Node used `localeCompare`, .NET a bare `OrderBy` (`Comparer<string>.Default` is `CurrentCulture`), Python ordinal `sorted()`. Measured on realistic agent keys, ordinal and locale disagree on two independent pairs — so keys differing by case, or by `_` against a letter, already hashed differently per SDK. All three are now ordinal.
- **`model_config`.** .NET emitted `null` where Node and Python emit `{}`, which made .NET's fingerprint differ from both for *every* declaration set that has ever existed. .NET now emits `{}`.

Both are pinned by `vested-ai-sdks/testdata/fingerprint-vectors.json`, a shared fixture the three SDKs assert against.

Intended git tag: `v0.6.0` (on the public mirror repo).

---

## v0.4.0 Release Notes

### v0.4.0 — feat: ERP identity on ToolContext (L-3)

`ToolContext` gains three nullable ERP/HR identity fields, populated from the incoming `ToolCallRequest` (proto fields 10-12):

| Field | Type | Default | Description |
|---|---|---|---|
| `employee_no` | `str` | `""` | Calling user's HR/ERP employee number. |
| `erp_identifier` | `str` | `""` | Calling user's ERP system identifier (e.g. SAP user ID). |
| `erp_department_identifiers` | `tuple[str, ...]` | `()` | ERP identifiers of every department the user belongs to in the run's org. |

All three default to `""` / `()` when the hub does not supply them (system runs, older hub versions). The proto binding (`connector_hub_pb2`) has been regenerated to include the new fields. Bumped to 0.4.0 (additive feature, backward-compatible).

**Migration:** No changes required. Existing handlers that do not use ERP identity continue to work identically. Read `ctx.employee_no`, `ctx.erp_identifier`, and `ctx.erp_department_identifiers` in your `handle()` method when you need to resolve which ERP record the tool call is acting on behalf of.

---

## v0.3.0 Release Notes

### v0.3.0 — feat: connector-declared tool sensitivity

`@tool` gains an optional `sensitivity` keyword parameter (`"read"`, `"write"`, `"destructive"`, `"external_call"`, `"medium"`). Omitting it (or passing `""`) leaves it unset; the hub defaults to `external_call`. The value is threaded into the wire `ToolDecl` proto (field 8) and included in the baseline fingerprint so a change in sensitivity triggers a hub reconcile. Invalid values raise `ValueError` at decoration time with a message listing the allowed values. Bumped to 0.3.0 (additive feature, backward-compatible).

**Migration:** No changes required. Existing `@tool` declarations without `sensitivity` continue to work identically. Add `sensitivity=` only when you want to advertise a specific risk level.

---

## v0.2.x Patch Notes

### v0.2.1 — fix: send non-empty baseline_fingerprint at Register

The hub short-circuits re-registration when the incoming fingerprint matches the value it has stored for the connector. Its in-memory store starts at `""`. In v0.2.0 the SDK sent `baseline_fingerprint=""` at every Register — that trivially matched the empty initial value, the hub returned `"accepted"` without forwarding to Laravel, and the connector's agents/tools never persisted to the DB. Symptom: SDK logs "registered with hub" but the admin-ui never shows any agents under the connector.

Fix: compute a deterministic SHA256 over the canonical agent + tool declarations and send it as `baseline_fingerprint`. Required upgrade.

### v0.2.0 — Initial Python release

First Python SDK implementation. asyncio + grpcio runtime. Decorator-first API (`@agent`, `@tool`). Pydantic v2 schema generation. Feature parity with PHP SDK v0.2.4 on the wire. Available on [PyPI](https://pypi.org/project/vested-connect-sdk/) (`pip install vested-connect-sdk`) and [Docker Hub](https://hub.docker.com/r/vestedai/vested-ai-connector-sdk-python).

## Next

[Connector protocol overview](protocol/overview.md)
