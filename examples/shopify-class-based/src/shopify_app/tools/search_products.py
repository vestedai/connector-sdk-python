"""shopify.insights.search_products — search products by title."""

from __future__ import annotations

from vested_connect import BaseModel, Field, ToolContext, ToolHandler, tool

from shopify_app.shopify_client import ShopifyClient


class Product(BaseModel):
    """A Shopify product summary."""

    product_id: int
    title: str
    vendor: str
    status: str
    price_range: str  # e.g. "9.99 – 29.99"


@tool(
    "shopify.insights.search_products",
    description=(
        "Search Shopify products by title. Returns up to 25 matching products "
        "with id, title, vendor, status, and price range."
    ),
    default_deadline_ms=15_000,
    max_result_bytes=65_536,
)
class SearchProducts(ToolHandler):
    class Args(BaseModel):
        query: str = Field(
            description="Search term matched against product title.",
        )
        limit: int = Field(
            default=10,
            ge=1,
            le=25,
            description="Max number of products to return (1–25).",
        )

    class Result(BaseModel):
        query: str
        products: list[Product]

    async def handle(  # type: ignore[override]
        self,
        args: Args,
        ctx: ToolContext,
    ) -> Result:
        async with ShopifyClient.from_env() as client:
            data = await client.get(
                "/admin/api/2024-10/products.json",
                params={"title": args.query, "limit": args.limit, "status": "active"},
            )

        products: list[Product] = []
        for p in data.get("products", []):
            # Compute a human-readable price range from the variants.
            prices = [
                float(v.get("price", "0"))
                for v in p.get("variants", [])
                if v.get("price")
            ]
            if prices:
                lo, hi = min(prices), max(prices)
                price_range = f"{lo:.2f}" if lo == hi else f"{lo:.2f} – {hi:.2f}"
            else:
                price_range = "—"

            products.append(
                Product(
                    product_id=int(p["id"]),
                    title=p.get("title", ""),
                    vendor=p.get("vendor", ""),
                    status=p.get("status", ""),
                    price_range=price_range,
                )
            )

        return SearchProducts.Result(query=args.query, products=products)
