"""Module scanner tests."""

from __future__ import annotations

import textwrap

import pytest

from vested_connect.runtime.scanner import scan_module
from vested_connect.tool import ToolDeclaration


@pytest.fixture
def example_package(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """Create a small example package with one @agent + two @tool classes."""
    pkg = tmp_path / "fixture_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(textwrap.dedent("""
        from .agent_mod import Insights
        from .tool_mod import EchoTool, AddTool
    """))
    (pkg / "agent_mod.py").write_text(textwrap.dedent("""
        from vested_connect import agent, Instruction

        @agent(
            key="fx.insights",
            name="Insights",
            model="openai:gpt-4o",
            instructions=[Instruction(type="system", position=0, body="x")],
        )
        class Insights:
            pass
    """))
    (pkg / "tool_mod.py").write_text(textwrap.dedent("""
        from vested_connect import tool, ToolHandler, BaseModel, Field

        @tool("fx.insights.echo", description="Echo back.")
        class EchoTool(ToolHandler):
            class Args(BaseModel):
                text: str = Field(description="text")
            async def handle(self, args, ctx):
                return {"echoed": args.text}

        @tool("fx.insights.add", description="Add two ints.")
        class AddTool(ToolHandler):
            class Args(BaseModel):
                a: int = Field(description="a")
                b: int = Field(description="b")
            async def handle(self, args, ctx):
                return {"sum": args.a + args.b}
    """))

    monkeypatch.syspath_prepend(str(tmp_path))
    yield "fixture_pkg"


def test_scan_module_collects_agents_and_tools(example_package: str) -> None:
    agents, tools = scan_module(example_package)
    assert len(agents) == 1
    assert agents[0].key == "fx.insights"
    assert set(tools.keys()) == {"fx.insights.echo", "fx.insights.add"}
    assert all(isinstance(t, ToolDeclaration) for t in tools.values())


def test_scan_module_raises_on_duplicate_tool_key(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pkg = tmp_path / "dup_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(textwrap.dedent("""
        from .a import A
        from .b import B
    """))
    (pkg / "a.py").write_text(textwrap.dedent("""
        from vested_connect import tool, ToolHandler, BaseModel
        @tool("ns.dup", description="x")
        class A(ToolHandler):
            class Args(BaseModel):
                pass
            async def handle(self, args, ctx): return {}
    """))
    (pkg / "b.py").write_text(textwrap.dedent("""
        from vested_connect import tool, ToolHandler, BaseModel
        @tool("ns.dup", description="x")
        class B(ToolHandler):
            class Args(BaseModel):
                pass
            async def handle(self, args, ctx): return {}
    """))

    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(RuntimeError, match="duplicate tool key ns.dup"):
        scan_module("dup_pkg")
