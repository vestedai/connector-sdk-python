"""shopify.insights.top_selling_products — top sellers from an analytics replica.

The Shopify REST API does not expose aggregated sales totals without a
custom report endpoint, so this tool queries an analytics-replica
Postgres database directly via asyncpg.

Set DATABASE_URL to enable the tool. If the variable is unset the tool
raises ToolValidationError with a clear message rather than silently
returning empty results.
"""

from __future__ import annotations

from vested_connect import (
    BaseModel,
    Field,
    ToolContext,
    ToolHandler,
    ToolValidationError,
    tool,
)

from shopify_app.db import get_pool

_TOOL_KEY = "shopify.insights.top_selling_products"

# SQL executed against the analytics replica. The schema here is a
# common Shopify data-warehouse pattern; adapt column names to match
# your own replica.
_SQL = """
SELECT
    product_id,
    product_title,
    SUM(quantity)            AS units_sold,
    SUM(price * quantity)    AS revenue
FROM order_line_items
WHERE
    order_created_at >= NOW() - ($1 * INTERVAL '1 day')
    AND financial_status = 'paid'
GROUP BY product_id, product_title
ORDER BY units_sold DESC
LIMIT $2
"""


class TopProduct(BaseModel):
    """A top-selling product summary from the analytics replica."""

    product_id: int
    title: str
    units_sold: int
    revenue: float


@tool(
    _TOOL_KEY,
    description=(
        "Return the top-selling products over a lookback window, ranked by units "
        "sold. Requires DATABASE_URL to point to an analytics replica that has an "
        "order_line_items table."
    ),
    default_deadline_ms=60_000,
    max_result_bytes=32_768,
)
class TopSellingProducts(ToolHandler):
    class Args(BaseModel):
        days: int = Field(
            default=30,
            ge=1,
            le=365,
            description="Lookback window in days (1–365). Defaults to 30.",
        )
        limit: int = Field(
            default=10,
            ge=1,
            le=50,
            description="Max products to return (1–50). Defaults to 10.",
        )

    class Result(BaseModel):
        window_days: int
        products: list[TopProduct]

    async def handle(  # type: ignore[override]
        self,
        args: Args,
        ctx: ToolContext,
    ) -> Result:
        pool = await get_pool()
        if pool is None:
            raise ToolValidationError(
                _TOOL_KEY,
                "DATABASE_URL not configured — this tool requires a direct "
                "connection to an analytics replica. Set DATABASE_URL and restart "
                "the worker.",
            )

        async with pool.acquire() as conn:  # type: ignore[attr-defined]
            rows = await conn.fetch(_SQL, args.days, args.limit)

        products = [
            TopProduct(
                product_id=int(row["product_id"]),
                title=str(row["product_title"]),
                units_sold=int(row["units_sold"]),
                revenue=float(row["revenue"]),
            )
            for row in rows
        ]

        return TopSellingProducts.Result(
            window_days=args.days,
            products=products,
        )
