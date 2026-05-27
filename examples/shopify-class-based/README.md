# Shopify connector walkthrough

Build a vested-ai connector for a Shopify store. Two agents (operations +
insights), three tools, deployed as a Docker worker. Builds on
[quickstart](../../docs/quickstart.md).

---

## What this example demonstrates

- `shopify.operations` agent — answers order-status questions via the
  Shopify Admin REST API
- `shopify.insights` agent — searches products and surfaces top-selling
  products from an analytics replica
- `httpx.AsyncClient` for async Shopify REST calls with
  `X-Shopify-Access-Token` authentication
- Optional `asyncpg` direct-DB path for analytics that the REST API
  cannot aggregate efficiently
- Class-based `@agent` / `@tool` decorators — one class per file, all
  wired by a single `scan_module("shopify_app")` call in `bootstrap.py`

---

## Prerequisites

- Python 3.10+
- A Shopify store with an **Admin API access token** (Private App or Custom
  App with `read_orders` and `read_products` scopes)
- A vested-ai connector token — see
  [quickstart §1](../../docs/quickstart.md#1-get-a-connector-token)
- Docker (for the containerised run)
- Postgres analytics replica *(optional)* — only needed for
  `top_selling_products`

---

## Layout

```
shopify-class-based/
├── bootstrap.py               # ConnectorApp.create().scan_module(...)
├── pyproject.toml
├── Dockerfile
├── .env.example
└── src/
    └── shopify_app/
        ├── __init__.py        # imports agents + tools so decorators fire
        ├── shopify_client.py  # httpx-based async REST client
        ├── db.py              # lazy asyncpg pool (optional)
        ├── agents/
        │   ├── operations.py  # @agent("shopify.operations", ...)
        │   └── insights.py    # @agent("shopify.insights", ...)
        └── tools/
            ├── order_status.py         # REST — GET /orders
            ├── search_products.py      # REST — GET /products
            └── top_selling_products.py # DB   — analytics replica
```

`scan_module("shopify_app")` walks the `shopify_app` package and collects
every class decorated with `@agent` or `@tool`. Agents and tools live in
separate sub-packages purely for readability — the scanner picks them up
regardless of file layout.

---

## Step-by-step

### 1. Install

```bash
cd vested-ai-sdks/python/examples/shopify-class-based
pip install -e .
```

This installs `vested-connect-sdk`, `httpx`, `asyncpg`, and `pydantic`.

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in the blanks:

```bash
cp .env.example .env
$EDITOR .env
```

| Variable | Description |
|---|---|
| `VESTED_CONNECTOR_TOKEN` | Your vested-ai connector token (`ct_…`) |
| `VESTED_CONNECTOR_HUB` | Hub address, e.g. `hub.vested.ai:4443` |
| `SHOPIFY_SHOP_DOMAIN` | Your store, e.g. `my-store.myshopify.com` |
| `SHOPIFY_ADMIN_TOKEN` | Admin API access token |
| `DATABASE_URL` | Postgres DSN for analytics replica *(optional)* |
| `LOG_LEVEL` | `INFO` (default) or `DEBUG` |

### 3. Run the worker

```bash
source .env   # or use dotenv / direnv
vested-connect worker --bootstrap=./bootstrap.py
```

Expected startup output:

```
INFO  vested_connect  Connected to hub hub.vested.ai:4443
INFO  vested_connect  Registered agent shopify.operations (1 tool)
INFO  vested_connect  Registered agent shopify.insights (2 tools)
INFO  vested_connect  Worker ready
```

Set `LOG_LEVEL=DEBUG` to see per-request timings for every Shopify REST
call and every DB query.

### 4. Verify in the admin UI

1. Open the vested-ai admin UI → **Connectors**.
2. Both agents appear under your connector namespace with a green status
   pill.
3. Open the **Test** tab on `shopify.operations`.
4. Run `{"order_identifier": "#1001"}` — an order result should appear
   within a few seconds.
5. Switch to `shopify.insights` and run
   `{"query": "t-shirt", "limit": 5"}` on `search_products`.

---

## Each tool in detail

### `shopify.operations.order_status`

Looks up a single Shopify order by its human-readable name (e.g.
`#1001`) or its numeric ID.

**Args**

| Field | Type | Description |
|---|---|---|
| `order_identifier` | `str` | Order name like `'#1001'` or numeric ID |

**Result**

| Field | Type |
|---|---|
| `order_id` | `int` |
| `name` | `str` — the `#NNN` display name |
| `status` | `str` — mirrors `financial_status` |
| `financial_status` | `str` — `paid`, `pending`, `refunded`, … |
| `fulfillment_status` | `str \| None` — `fulfilled`, `partial`, `null` |
| `total_price` | `str` — e.g. `"59.99"` |
| `currency` | `str` — ISO-4217, e.g. `"USD"` |
| `line_items` | `list[LineItem]` — product_id, title, quantity, price |

**Shopify API calls**

- Numeric ID → `GET /admin/api/2024-10/orders/{id}.json`
- Order name → `GET /admin/api/2024-10/orders.json?name=%231001&status=any&limit=1`

Authentication is via the `X-Shopify-Access-Token` header set on the
`httpx.AsyncClient` instance inside `ShopifyClient`.

---

### `shopify.insights.search_products`

Searches active products by title.

**Args**

| Field | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | — | Search term matched against product title |
| `limit` | `int` | `10` | Max results, 1–25 |

**Result** — `{ "query": str, "products": list[Product] }`

Each `Product` has: `product_id`, `title`, `vendor`, `status`,
`price_range` (e.g. `"9.99 – 29.99"`).

**Shopify API call**

```
GET /admin/api/2024-10/products.json?title={query}&limit={limit}&status=active
```

The price range is computed client-side from the `variants` array
returned by Shopify — one line of Python rather than a second API call.

---

### `shopify.insights.top_selling_products`

Returns the top-selling products over a lookback window, ranked by units
sold.

**Args**

| Field | Type | Default | Description |
|---|---|---|---|
| `days` | `int` | `30` | Lookback window, 1–365 |
| `limit` | `int` | `10` | Max products, 1–50 |

**Result** — `{ "window_days": int, "products": list[TopProduct] }`

Each `TopProduct` has: `product_id`, `title`, `units_sold`, `revenue`.

**Why not REST?** — Shopify's REST API does not expose aggregated sales
totals without a custom report endpoint or the Plus-tier Analytics API.
For most merchants the practical path is a nightly export into a Postgres
analytics replica, which this tool queries directly.

---

## The optional DB path

`top_selling_products` uses `asyncpg` to run a SQL query directly
against an analytics-replica Postgres database.

**When `DATABASE_URL` is unset** the tool raises `ToolValidationError`
with a clear message:

```
shopify.insights.top_selling_products: DATABASE_URL not configured — this
tool requires a direct connection to an analytics replica. Set DATABASE_URL
and restart the worker.
```

The LLM receives this error as a tool result and relays it to the user
in natural language.

**Pool lifecycle** — `db.get_pool()` lazily creates a module-level
`asyncpg.Pool` (min 1 / max 5 connections) on first call and reuses it
for the process lifetime. The SDK does not yet expose a shutdown hook, so
pool teardown is best-effort on SIGTERM; the OS reclaims sockets when the
process exits.

**Expected schema** — the SQL in `top_selling_products.py` targets a
table named `order_line_items` with columns `product_id`,
`product_title`, `quantity`, `price`, `order_created_at`, and
`financial_status`. Adapt the query to match your own replica schema.

---

## Docker

### Build and run

```bash
# from the shopify-class-based/ directory
docker build -t shopify-connector .

docker run --rm \
  --env-file .env \
  shopify-connector
```

### What the image contains

The `Dockerfile` is minimal — it copies `pyproject.toml`, `src/`, and
`bootstrap.py`, runs `pip install`, and starts the worker:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
COPY bootstrap.py ./
RUN pip install --no-cache-dir .
CMD ["vested-connect", "worker", "--bootstrap=./bootstrap.py"]
```

To use a specific vested-connect-sdk version, pin it in `pyproject.toml`
before building.

---

## Customizing

### Adding a new tool

1. Create `src/shopify_app/tools/my_tool.py`.
2. Decorate a `ToolHandler` subclass with `@tool("shopify.<agent>.my_tool", ...)`.
3. Import the module in `src/shopify_app/__init__.py`:
   ```python
   from shopify_app.tools import my_tool  # noqa: F401
   ```
4. Restart the worker — the new tool appears in the admin UI automatically.

The `@tool` key prefix determines which agent the tool is scoped to. A
tool keyed `shopify.operations.my_tool` is automatically attached to the
`shopify.operations` agent.

### Adding a new agent

Decorate a marker class in `src/shopify_app/agents/`:

```python
from vested_connect import Instruction, agent

@agent(
    key="shopify.support",
    name="Shopify Support",
    model="openai:gpt-4o-mini",
    description="Handles refund and support workflows.",
    instructions=[
        Instruction(type="system", position=0, body="You handle refunds..."),
    ],
)
class Support:
    pass
```

Import it in `__init__.py` and prefix your tool keys with
`shopify.support.<tool_name>`.

### Scoping a tool to multiple agents

The SDK matches tools to agents by key prefix. To make the same tool
callable from two agents, register it under each agent's key — either as
two separate `@tool` classes that share the same handler logic, or by
extracting the logic into a shared helper and calling it from both.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `VESTED_CONNECTOR_TOKEN invalid` | Token revoked or wrong | Re-issue in admin UI |
| `SHOPIFY_SHOP_DOMAIN is required` | Env var missing | Check `.env` or shell |
| `ShopifyAuthError: … 401` | Admin token expired or wrong scopes | Regenerate in Shopify Partners |
| `ShopifyNotFoundError: … 404` | Order ID does not exist | Verify identifier |
| `DATABASE_URL not configured` | Missing env var for DB tool | Set `DATABASE_URL` or avoid calling `top_selling_products` |
| Pool connection refused | Replica not reachable | Check VPN / firewall / DSN |
