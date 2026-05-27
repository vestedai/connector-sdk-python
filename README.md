# Vested AI Connector SDK (Python)

![Build](https://img.shields.io/github/actions/workflow/status/vestedsystems/connector-sdk-python/ci.yml?branch=main)
![License](https://img.shields.io/github/license/vestedsystems/connector-sdk-python)
![Python](https://img.shields.io/badge/python-%5E3.11-blue)

Connect any Python service to the Vested AI platform. The SDK opens a long-lived gRPC stream to the hub, declares agents and tools over that stream, and dispatches tool calls to your handler code — no polling, no webhook setup, no managing your own LLM client. The hub handles model selection, prompt composition, and conversation state; your connector owns the business logic.

## Install

> **Coming soon to PyPI.** The package will be published as `vested-connect-sdk` when v0.2.0 ships. Until then, install from source.

```bash
pip install vested-connect-sdk
```

## 5-Line Connector

```python
from vested_connect import ConnectorApp, agent, tool, ToolHandler, ToolContext, BaseModel, Field

@agent(key="myapp.orders", name="Orders", instruction="You help users look up their orders.")
class OrdersAgent: ...

@tool(agent_key="myapp.orders", key="myapp.orders.get", name="Get order", description="Returns an order by ID.")
class GetOrder(ToolHandler):
    class Args(BaseModel):
        id: str = Field(description="Order ID")
    async def handle(self, args: Args, ctx: ToolContext) -> dict:
        return {"status": "shipped"}  # replace with a real lookup

ConnectorApp.create().scan_module(__name__).run(token=..., hub="hub.example.com:4443")
```

## What This Is

A **connector** is a long-lived worker process that registers one or more agents with the Vested AI hub. Each agent carries a model selection, a set of instruction blocks, and a set of tool definitions. Admins can override instruction bodies and disable tools in the admin UI; the connector's declared baseline is the floor that overrides are layered on top of. The hub routes LLM tool calls back to the connector over the same stream; the connector dispatches them to your handler code and returns results.

This differs from writing your own LLM client. The connector does not call the LLM directly. It registers capability and responds to callbacks. Prompt composition, model routing, conversation history, streaming to end users — all of that lives in the hub. The connector's surface area is: "declare what agents exist, implement what the tools do."

## Documentation

| Document | What's in it |
|---|---|
| [Quickstart](docs/quickstart.md) | Install, write your first agent + tool, run the worker, verify in the admin UI |
| [Concepts](docs/concepts.md) | Agents, tools, instructions, baselines vs overrides, inheritance state machine, reconciliation |
| [API reference](docs/api.md) | `ConnectorApp`, `@agent`, `@tool`, `ToolHandler`, `ToolContext` |
| [Operations](docs/operations.md) | Docker, env vars, observability, reconnect supervisor, asyncio notes, gotchas |
| [Upgrading](docs/upgrading.md) | Coming from the PHP SDK; v0.2.x patch notes |
| [Doc index](docs/README.md) | Full table of contents including protocol reference |

## License + Status

MIT. Current release: **v0.2.0-dev** (asyncio + grpcio runtime, decorator API, Pydantic v2 schema generation). Pre-release; not yet on PyPI.
