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
