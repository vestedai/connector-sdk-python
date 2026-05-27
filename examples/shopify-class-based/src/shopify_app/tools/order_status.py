"""shopify.operations.order_status — look up an order by name or numeric ID."""

from __future__ import annotations

from vested_connect import BaseModel, Field, ToolContext, ToolHandler, tool

from shopify_app.shopify_client import ShopifyClient


class LineItem(BaseModel):
    """A single line item on a Shopify order."""

    product_id: int | None
    title: str
    quantity: int
    price: str


@tool(
    "shopify.operations.order_status",
    description=(
        "Look up a Shopify order by its name (e.g. '#1001') or numeric order ID. "
        "Returns status, financial status, fulfilment status, line items, total price, "
        "and currency."
    ),
    default_deadline_ms=30_000,
    max_result_bytes=32_768,
)
class OrderStatus(ToolHandler):
    class Args(BaseModel):
        order_identifier: str = Field(
            description="Either the order name like '#1001' or the numeric order ID.",
        )

    class Result(BaseModel):
        order_id: int
        name: str
        status: str
        financial_status: str
        fulfillment_status: str | None
        total_price: str
        currency: str
        line_items: list[LineItem]

    async def handle(  # type: ignore[override]
        self,
        args: Args,
        ctx: ToolContext,
    ) -> Result:
        identifier = args.order_identifier.strip()

        async with ShopifyClient.from_env() as client:
            if identifier.lstrip("#").isdigit():
                # Numeric ID — fetch directly.
                numeric_id = identifier.lstrip("#")
                data = await client.get(
                    f"/admin/api/2024-10/orders/{numeric_id}.json"
                )
                order = data["order"]
            else:
                # Order name like '#1001'.
                data = await client.get(
                    "/admin/api/2024-10/orders.json",
                    params={"name": identifier, "status": "any", "limit": 1},
                )
                orders = data.get("orders", [])
                if not orders:
                    raise ValueError(f"No order found for identifier: {identifier!r}")
                order = orders[0]

        line_items = [
            LineItem(
                product_id=item.get("product_id"),
                title=item.get("title", ""),
                quantity=int(item.get("quantity", 0)),
                price=item.get("price", "0.00"),
            )
            for item in order.get("line_items", [])
        ]

        return OrderStatus.Result(
            order_id=int(order["id"]),
            name=order.get("name", ""),
            status=order.get("financial_status", ""),  # top-level status alias
            financial_status=order.get("financial_status", ""),
            fulfillment_status=order.get("fulfillment_status"),
            total_price=order.get("total_price", "0.00"),
            currency=order.get("currency", ""),
            line_items=line_items,
        )
