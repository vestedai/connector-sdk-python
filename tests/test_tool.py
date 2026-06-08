from __future__ import annotations

from typing import Any

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


# ---------------------------------------------------------------------------
# sensitivity tests
# ---------------------------------------------------------------------------


def test_tool_decorator_sensitivity_default_is_empty() -> None:
    """Omitting sensitivity defaults to empty string (hub will apply its own default)."""
    decl = InventoryCheck.__vested_tool__  # type: ignore[attr-defined]
    assert decl.sensitivity == ""


def test_tool_decorator_stamps_valid_sensitivity() -> None:
    """A valid sensitivity value is stamped onto the ToolDeclaration."""

    @tool("acme.delete_item", description="Destroy something.", sensitivity="destructive")
    class DeleteItem(ToolHandler):
        class Args(BaseModel):
            item_id: str

        async def handle(self, args: Args, ctx: ToolContext) -> dict[str, Any]:  # type: ignore[override]
            return {}

    decl = DeleteItem.__vested_tool__  # type: ignore[attr-defined]
    assert decl.sensitivity == "destructive"


def test_tool_decorator_all_valid_sensitivities_accepted() -> None:
    """Each member of TOOL_SENSITIVITIES is accepted without raising."""
    from vested_connect.tool import TOOL_SENSITIVITIES

    for sens in TOOL_SENSITIVITIES:

        @tool(f"acme.sens.{sens}", description="test", sensitivity=sens)
        class _T(ToolHandler):
            class Args(BaseModel):
                x: str

            async def handle(self, args: Args, ctx: ToolContext) -> dict[str, Any]:  # type: ignore[override]
                return {}

        decl = _T.__vested_tool__  # type: ignore[attr-defined]
        assert decl.sensitivity == sens


def test_tool_decorator_rejects_invalid_sensitivity() -> None:
    """An unrecognised sensitivity value must raise ValueError at decoration time."""
    with pytest.raises(ValueError, match="sensitivity must be one of"):
        @tool("acme.bad_sens", description="bad", sensitivity="super_dangerous")
        class _Bad(ToolHandler):
            class Args(BaseModel):
                x: str

            async def handle(self, args: Args, ctx: ToolContext) -> dict[str, Any]:  # type: ignore[override]
                return {}


def test_tool_decorator_rejects_invalid_sensitivity_includes_allowed() -> None:
    """The ValueError message lists the allowed values."""
    with pytest.raises(ValueError, match="read") as exc_info:
        @tool("acme.bad2", description="bad", sensitivity="unknown_val")
        class _Bad2(ToolHandler):
            class Args(BaseModel):
                x: str

            async def handle(self, args: Args, ctx: ToolContext) -> dict[str, Any]:  # type: ignore[override]
                return {}

    msg = str(exc_info.value)
    assert "unknown_val" in msg
