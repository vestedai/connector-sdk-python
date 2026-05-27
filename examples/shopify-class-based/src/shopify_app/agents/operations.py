"""shopify.operations agent — order and customer service lookups."""

from vested_connect import Instruction, agent


@agent(
    key="shopify.operations",
    name="Shopify Operations",
    model="openai:gpt-4o",
    description="Looks up orders, customers, and order status in Shopify.",
    instructions=[
        Instruction(
            type="system",
            position=0,
            body=(
                "You help customer-service operators answer order-status questions "
                "quickly and accurately. When an order is found, always state its "
                "current status, financial status, and fulfilment status in your "
                "first sentence. If a tool returns no results, say so plainly rather "
                "than guessing."
            ),
        ),
        Instruction(
            type="task",
            position=1,
            body=(
                "For order questions use order_status with the order name "
                "(e.g. '#1001') or the numeric order ID. Never fabricate order "
                "details — if the lookup returns nothing, ask the operator to "
                "verify the identifier."
            ),
        ),
    ],
)
class Operations:
    # Marker class. The SDK @agent scanner requires no methods.
    pass
