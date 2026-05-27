# Quickstart

Reading time: ~15 minutes. By the end, a connector worker is running locally, registered with the hub, and the agent is visible in the admin UI.

## Prerequisites

- **Python 3.11+**
- **pip** (or another package installer)
- A running Vested AI instance with admin access

## 1. Get a Connector Token

Sign in to the admin UI. Navigate to **Integrations → Add integration**. Fill in:

- **Namespace** — a short identifier for your connector (e.g., `myapp`). All agent and tool keys must start with this namespace.
- **Name** — human-readable label.

Click **Create**. Copy the token shown — it is displayed only once.

## 2. Create a Project

```bash
mkdir my-connector && cd my-connector
python -m venv .venv && source .venv/bin/activate
pip install vested-connect-sdk
```

Expected directory shape after install:

```
my-connector/
  .venv/
  bootstrap.py          ← you will create this
  src/
    agents.py
    tools.py
```

## 3. Declare Your First Agent and Tool

Create `src/agents.py`:

```python
from vested_connect import agent, Instruction

@agent(
    key="myapp.greeting",
    name="Greeting Agent",
    description="Says hello",
)
@agent.model(provider="openai", name="gpt-4o")
@agent.instruction(Instruction(type="system", position=0, body="You greet users warmly and briefly."))
class GreetingAgent: ...
```

Create `src/tools.py`:

```python
from vested_connect import tool, ToolHandler, ToolContext, BaseModel, Field

class HelloArgs(BaseModel):
    name: str = Field(description="The person's name to greet")

class HelloResult(BaseModel):
    message: str

@tool(
    agent_key="myapp.greeting",
    key="myapp.greeting.hello",
    name="Say hello",
    description="Returns a greeting for the given name.",
)
class SayHello(ToolHandler):
    async def handle(self, args: HelloArgs, ctx: ToolContext) -> HelloResult:
        return HelloResult(message=f"Hello, {args.name}!")
```

The `Args` model is a plain Pydantic `BaseModel`. The SDK auto-generates the JSON Schema for the `input_schema_json` field from it. Return a dict or a Pydantic model for the output.

## 4. Wire bootstrap.py

Create `bootstrap.py` in the project root:

```python
import src.agents  # noqa: F401 — registers @agent classes
import src.tools   # noqa: F401 — registers @tool classes

from vested_connect import ConnectorApp

app = ConnectorApp.create().scan_module("src.agents").scan_module("src.tools")
```

`bootstrap.py` is loaded by the CLI. It must ensure all decorated classes are imported before `ConnectorApp` is returned or the module scan runs. The decorator registration is side-effectful; importing the module is sufficient.

## 5. Run the Worker Locally

```bash
VESTED_CONNECTOR_TOKEN=eyJ… \
VESTED_CONNECTOR_HUB=ai-connect.example.com:4443 \
vested-connect worker --bootstrap=./bootstrap.py
```

Alternatively, invoke via the Python module directly:

```bash
python -m vested_connect.cli worker --bootstrap=./bootstrap.py
```

On success:

```
connected to hub  connector_id=42 namespace=myapp max_concurrent=16
```

The worker stays running. Leave it running for step 6.

To use plaintext gRPC against a local dev hub, add `--insecure`.

## 6. Verify in the Admin UI

1. Navigate to **Integrations**. The connector's status badge should read **active** (green).
2. Navigate to **Agents**. The `myapp.greeting` agent should appear with source column showing your connector name.
3. Open the agent detail. The version is auto-published (first registration publishes immediately).
4. Open the **Test** tab on the agent. Invoke the `myapp.greeting.hello` tool with `{"name": "World"}`. The response should be `{"message": "Hello, World!"}`.

## Next

[Concepts](concepts.md)
