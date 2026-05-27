import pytest

from vested_connect import BaseModel, Field, ToolContext, ToolHandler, tool
from vested_connect.errors import ToolValidationError
from vested_connect.tool import validate_args


@tool("acme.insights.inventory_check", description="Check stock for SKUs.")
class InventoryCheck(ToolHandler):
    class Args(BaseModel):
        skus: list[str] = Field(description="SKUs to look up.")
        threshold: int = Field(default=0, description="Min threshold.")

    class Result(BaseModel):
        items: list[dict[str, object]]

    async def handle(self, args: Args, ctx: ToolContext) -> Result:  # type: ignore[override]
        return InventoryCheck.Result(items=[{"sku": s} for s in args.skus])


def test_tool_decorator_generates_input_schema_with_descriptions() -> None:
    decl = InventoryCheck.__vested_tool__  # type: ignore[attr-defined]
    assert decl.key == "acme.insights.inventory_check"
    assert decl.description == "Check stock for SKUs."
    schema = decl.input_schema
    props = schema["properties"]
    assert props["skus"]["description"] == "SKUs to look up."
    assert props["threshold"]["description"] == "Min threshold."
    assert "skus" in schema["required"]


def test_tool_decorator_generates_output_schema() -> None:
    decl = InventoryCheck.__vested_tool__  # type: ignore[attr-defined]
    assert "items" in decl.output_schema["properties"]


def test_validate_args_accepts_native_array() -> None:
    decl = InventoryCheck.__vested_tool__  # type: ignore[attr-defined]
    args = validate_args(decl, '{"skus": ["A", "B"], "threshold": 5}')
    assert args.skus == ["A", "B"]  # type: ignore[attr-defined]
    assert args.threshold == 5  # type: ignore[attr-defined]


def test_validate_args_rejects_stringified_array() -> None:
    decl = InventoryCheck.__vested_tool__  # type: ignore[attr-defined]
    with pytest.raises(ToolValidationError):
        validate_args(decl, '{"skus": "[\\"A\\", \\"B\\"]"}')


def test_validate_args_rejects_missing_required() -> None:
    decl = InventoryCheck.__vested_tool__  # type: ignore[attr-defined]
    with pytest.raises(ToolValidationError):
        validate_args(decl, '{"threshold": 5}')


def test_tool_decorator_rejects_non_handler_class() -> None:
    with pytest.raises(TypeError, match="must subclass ToolHandler"):
        @tool("bad", description="x")  # type: ignore[arg-type]
        class Bad:
            pass


def test_tool_decorator_rejects_missing_args_model() -> None:
    with pytest.raises(TypeError, match="must define inner Args"):
        @tool("bad", description="x")
        class Bad(ToolHandler):
            pass


def test_tool_context_construction() -> None:
    ctx = ToolContext(
        org_id=1, agent_key="a", run_id="r1",
        conversation_id="c1", user_email="u@example.com", user_id=42,
    )
    assert ctx.org_id == 1
    assert ctx.agent_key == "a"
