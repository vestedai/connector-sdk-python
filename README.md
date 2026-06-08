# Vested AI Connector SDK (Python)

![Build](https://img.shields.io/github/actions/workflow/status/vestedai/connector-sdk-python/ci.yml?branch=main)
![PyPI](https://img.shields.io/pypi/v/vested-connect-sdk)
![License](https://img.shields.io/github/license/vestedai/connector-sdk-python)
![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)

Connect any Python service to the Vested AI platform. The SDK opens a long-lived gRPC stream to the hub, declares agents and tools over that stream, and dispatches tool calls to your handler code — no polling, no webhook setup, no managing your own LLM client. The hub handles model selection, prompt composition, and conversation state; your connector owns the business logic.

## Install

```bash
pip install vested-connect-sdk
```

Or run the Docker image: `vestedai/vested-ai-connector-sdk-python:0.2.0` (also `:latest`, multi-arch amd64/arm64).

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

MIT. Current release: **v0.3.0** (asyncio + grpcio runtime, decorator API, Pydantic v2 schema generation, connector-declared tool sensitivity). On PyPI as [`vested-connect-sdk`](https://pypi.org/project/vested-connect-sdk/) and Docker Hub as [`vestedai/vested-ai-connector-sdk-python`](https://hub.docker.com/r/vestedai/vested-ai-connector-sdk-python).

## Other language SDKs

Same wire protocol, same hub — [all four SDKs](../README.md) are at feature parity (including connector-declared tool sensitivity):

- [PHP](../php/README.md) — Packagist `vested-ai/connector-sdk-php`
- [Node.js](../node/README.md) — npm `@vested-ai/connector-sdk`
- [C# / .NET](../dotnet/README.md) — NuGet `VestedAI.ConnectorSdk`
