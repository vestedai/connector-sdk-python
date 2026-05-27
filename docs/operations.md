# Operations

## Docker

A minimal customer Dockerfile (the official base image ships in H-9):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bootstrap.py .
COPY src ./src

ENTRYPOINT ["vested-connect", "worker", "--bootstrap=/app/bootstrap.py"]
```

The entrypoint reads `VESTED_CONNECTOR_TOKEN` and `VESTED_CONNECTOR_HUB` from the environment. If neither `--bootstrap` nor `--hub` is given on the CLI, the worker reads them from env vars.

Run as a single long-lived container (`replicas: 1` per token in Kubernetes). Graceful shutdown on SIGTERM: in-flight tool calls drain for up to 30 seconds before the process exits.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `VESTED_CONNECTOR_TOKEN` | Yes | — | JWT from the admin UI (Integrations → Add). Use `--token-stdin` for systemd credentials. |
| `VESTED_CONNECTOR_HUB` | Yes | — | Hub address as `host:port`, e.g. `ai-connect.example.com:4443`. |
| `LOG_LEVEL` | No | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. Read in `bootstrap.py`; the SDK itself does not read this variable. |

For secrets management, `--token-stdin` lets you pipe the token from any credential provider:

```bash
# systemd credential
cat "$CREDENTIALS_DIRECTORY/vested-token" | vested-connect worker --bootstrap=./bootstrap.py --token-stdin

# Vault / AWS SSM / SOPS — same pattern
vault kv get -field=token secret/vested | vested-connect worker --bootstrap=./bootstrap.py --token-stdin
```

---

## Observability

**Structured log fields** present on every log line emitted by the SDK (via `logging.LoggerAdapter` extra fields):

| Field | Present on |
|---|---|
| `connector_id` | All lines after HelloAck |
| `invocation_id` | Tool-call lines |
| `agent_key` | Tool-call lines |
| `tool_key` | Tool-call lines |
| `duration_ms` | Tool-call completion |

Log output is plain-text by default. To emit JSON logs, configure a JSON formatter on the root logger in `bootstrap.py`:

```python
import logging, json

class JsonFormatter(logging.Formatter):
    def format(self, record):
        d = {"level": record.levelname, "msg": record.getMessage(),
             **getattr(record, "extra", {})}
        return json.dumps(d)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.getLogger("vested_connect").addHandler(handler)
```

**Key log events by level:**

- `INFO` — `connected to hub` (with `connector_id`, `namespace`, `max_concurrent`); `stream closed`; `drain complete`; `shutdown requested`
- `WARNING` — `hub session ended, reconnecting` (with `delay_ms`, `handshake_completed`, `last_exit`); `GoAway from hub`
- `ERROR` — `token rejected`; `register issue`; `session ended` (with exception class + message)

**Heartbeat**: the SDK sends a `Heartbeat` frame every 20 seconds. The hub replies with `HeartbeatAck`. No heartbeat acknowledgement within the idle-timeout window (30 s) causes the hub to send `GoAway{idle}`.

**Loggers**: all SDK log records use `vested_connect.*` logger names. To silence the SDK while keeping your own logs, configure:

```python
logging.getLogger("vested_connect").setLevel(logging.WARNING)
```

---

## Reconnect + Supervisor

`ConnectorApp.run()` embeds a supervisor loop. The lifecycle is:

```
supervisor loop
  └── new session (asyncio task)
        ├── open gRPC stream
        ├── Hello/HelloAck
        ├── Register/RegisterAck  ← handshake_completed = True
        ├── steady-state (tool calls + heartbeats)
        └── disconnect / GoAway / error
              ↓
        if signal: exit 0
        if token rejected: exit 78 (EX_CONFIG)
        if handshake completed: reset backoff
        sleep(backoff.next())
        → new session
```

**Backoff schedule**: 1 s → 2 s → 4 s → 8 s → 16 s → 30 s (cap). Each interval has ±20% random jitter. A session that completed handshake before disconnecting resets the backoff to 1 s — hub deploys and node maintenance cause fast reconnect. A session that failed before handshake (hub down, network partition) keeps backing off.

SIGTERM during the inter-attempt sleep is caught immediately — the signal handler is installed at the supervisor level, not per session.

Token rotation sends `GoAway{token_rotated}` on the active stream. The process exits with code 78. Redeploy with the new token; the supervisor does not retry on exit 78.

---

## Signal Handling

The supervisor installs handlers for `SIGTERM` and `SIGINT` (Ctrl-C) at startup using `asyncio`'s `loop.add_signal_handler()`. On signal receipt:

1. In-flight tool calls are allowed to complete up to their remaining `deadline_ms`.
2. The gRPC stream is half-closed.
3. The process exits with code `0`.

Do not install competing signal handlers in `bootstrap.py`. If your application needs signal hooks, register them before calling `ConnectorApp.run()` and chain to the existing handlers.

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Clean shutdown (SIGTERM, SIGINT, or hub GoAway that is not terminal). |
| `78` | Token rejected (`EX_CONFIG`). A configuration change (new token) is required before retry. |

All other non-zero exit codes indicate an unexpected error. Process managers should restart on non-78 exits.

---

## asyncio Notes

The SDK runs the entire supervisor in a single asyncio event loop. Tool handlers are `async def`; they share the loop with the gRPC stream reader. Follow these rules to avoid blocking the event loop:

- **Never use blocking I/O** (`requests.get`, synchronous `psycopg2`, etc.) directly in a handler. Use async alternatives (`httpx`, `asyncpg`, etc.) or wrap in `asyncio.to_thread()`.
- **Database connections**: use an async connection pool (e.g. `asyncpg`, `sqlalchemy[asyncio]`). One pool sized to your concurrency expectation is the correct pattern. A single shared synchronous connection will serialize all queries.
- **CPU-bound work**: offload to `asyncio.to_thread()` or a `ProcessPoolExecutor` so it does not block heartbeats.

```python
@tool(agent_key="myns.data", key="myns.data.fetch", name="Fetch data", description="Fetches remote data.")
class FetchData(ToolHandler):
    class Args(BaseModel):
        url: str

    async def handle(self, args: Args, ctx: ToolContext) -> dict:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(args.url)
            r.raise_for_status()
            return {"body": r.text}
```

---

## Deployment Recipes

**Kubernetes** — set `replicas: 1` per connector token; set `VESTED_CONNECTOR_TOKEN` from a Secret; set `terminationGracePeriodSeconds: 45` (longer than the 30 s drain window).

**systemd** — pipe the token via `--token-stdin` from `$CREDENTIALS_DIRECTORY`; set `Restart=on-failure` and `RestartSec=5`.

The official Dockerfile for the Python SDK lands in H-9. Until then, base on `python:3.12-slim` as shown in the Docker section above.

---

## Troubleshooting

**`connector_unavailable`**
The tool dispatch arrived while the connector was disconnected. Check `hub session ended, reconnecting` in the connector logs. Verify the supervisor is running and not stuck on exit 78.

**`tool_call_timeout`**
A tool handler exceeded `deadline_ms`. Either increase `deadline_ms` in `@tool(deadline_ms=...)`, or speed up the handler (add timeouts to outbound HTTP calls, cache expensive lookups, etc.).

**`tool_call_invalid_result`**
The handler returned data that does not conform to the declared output schema. Check that the return value matches your `output_schema` (or the inferred schema from the return type annotation).

**Event loop blocking**
The SDK logs `WARNING vested_connect.worker: event loop blocked for Xms` when a handler call takes longer than 100 ms without any `await`. The handler is using synchronous I/O. Wrap it with `asyncio.to_thread()`.

## Next

[Upgrading](upgrading.md)
