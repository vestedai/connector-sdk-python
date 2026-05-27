"""shopify_app — generic Shopify connector package.

Importing this package registers all agents and tools with the SDK
scanner. The order matters: agents must be imported before tools so
that the agent keys are declared first.
"""

from shopify_app.agents import insights, operations  # noqa: F401
from shopify_app.tools import (  # noqa: F401
    order_status,
    search_products,
    top_selling_products,
)
