"""shopify.insights agent — product search and sales analytics."""

from vested_connect import Instruction, agent


@agent(
    key="shopify.insights",
    name="Shopify Insights",
    model="openai:gpt-4o",
    description="Answers product and sales-trend questions for the merchant.",
    instructions=[
        Instruction(
            type="system",
            position=0,
            body=(
                "You help merchants discover products and understand sales trends. "
                "When presenting metrics, always state the time window and any "
                "filters that were applied. Default to the last 30 days when the "
                "merchant does not specify a date range."
            ),
        ),
        Instruction(
            type="task",
            position=1,
            body=(
                "For 'what is selling' questions use top_selling_products. "
                "For product search use search_products. After presenting results, "
                "suggest one concrete follow-up action when appropriate "
                "(e.g. 'Want me to search for similar products?')."
            ),
        ),
    ],
)
class Insights:
    # Marker class. The SDK @agent scanner requires no methods.
    pass
