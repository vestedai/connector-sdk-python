import pytest

from vested_connect.errors import ConnectorError
from vested_connect.tool_binding import resolve_bindings, validate_bindings


class _Agent:
    def __init__(self, key: str) -> None:
        self.key = key


class _Tool:
    def __init__(self, key: str, agents: tuple[str, ...] = ()) -> None:
        self.key = key
        self.agents = agents


def _map(*tools: _Tool) -> dict[str, _Tool]:
    return {t.key: t for t in tools}


def test_falls_back_to_namespace_prefix_when_agents_omitted() -> None:
    bound = resolve_bindings(
        [_Agent("erp.data"), _Agent("erp.retail")], _map(_Tool("erp.data.run_sql"))
    )
    assert [t.key for t in bound["erp.data"]] == ["erp.data.run_sql"]
    assert bound["erp.retail"] == []


def test_binds_to_each_named_agent() -> None:
    bound = resolve_bindings(
        [_Agent("erp.data"), _Agent("erp.retail")],
        _map(_Tool("erp.data.run_sql", ("erp.data", "erp.retail"))),
    )
    assert len(bound["erp.data"]) == 1
    assert len(bound["erp.retail"]) == 1


def test_present_list_is_authoritative_not_additive() -> None:
    """The key names erp.data; the list names only erp.retail. The list wins."""
    bound = resolve_bindings(
        [_Agent("erp.data"), _Agent("erp.retail")],
        _map(_Tool("erp.data.run_sql", ("erp.retail",))),
    )
    assert bound["erp.data"] == []
    assert len(bound["erp.retail"]) == 1


def test_star_binds_every_declared_agent() -> None:
    bound = resolve_bindings(
        [_Agent("erp.data"), _Agent("erp.retail"), _Agent("erp.sales")],
        _map(_Tool("erp.shared.ping", ("*",))),
    )
    assert all(len(v) == 1 for v in bound.values())


def test_empty_list_treated_as_omitted() -> None:
    bound = resolve_bindings([_Agent("erp.data")], _map(_Tool("erp.data.run_sql", ())))
    assert len(bound["erp.data"]) == 1


def test_bound_tools_are_ordinally_sorted() -> None:
    bound = resolve_bindings(
        [_Agent("erp.data")],
        _map(
            _Tool("erp.data.b", ("erp.data",)),
            _Tool("erp.data.A", ("erp.data",)),
            _Tool("erp.data.a", ("erp.data",)),
        ),
    )
    assert [t.key for t in bound["erp.data"]] == [
        "erp.data.A",
        "erp.data.a",
        "erp.data.b",
    ]


def test_unknown_agent_key_raises() -> None:
    with pytest.raises(ConnectorError, match="erp.nope"):
        validate_bindings(
            [_Agent("erp.data")],
            _map(_Tool("erp.data.run_sql", ("erp.nope",))),
            lambda _m: None,
        )


def test_star_mixed_with_explicit_keys_raises() -> None:
    with pytest.raises(ConnectorError):
        validate_bindings(
            [_Agent("erp.data")],
            _map(_Tool("erp.data.run_sql", ("*", "erp.data"))),
            lambda _m: None,
        )


def test_key_prefix_absent_from_list_warns() -> None:
    warnings: list[str] = []
    validate_bindings(
        [_Agent("erp.data"), _Agent("erp.retail")],
        _map(_Tool("erp.data.run_sql", ("erp.retail",))),
        warnings.append,
    )
    assert any("erp.data.run_sql" in w and "erp.data" in w for w in warnings)


def test_tool_outside_every_namespace_is_legal_when_it_names_agents() -> None:
    """Legal PRECISELY because it names its agents."""
    agents = [_Agent("erp.data"), _Agent("erp.retail")]
    tools = _map(_Tool("erp.shared.run_sql", ("erp.data", "erp.retail")))

    validate_bindings(agents, tools, lambda _m: None)

    bound = resolve_bindings(agents, tools)
    assert len(bound["erp.data"]) == 1
    assert len(bound["erp.retail"]) == 1


def test_tool_matching_no_agent_and_naming_none_raises() -> None:
    """Nothing could ever call it, and that is never intentional."""
    with pytest.raises(ConnectorError, match="erp.shared.orphan"):
        validate_bindings(
            [_Agent("erp.data")], _map(_Tool("erp.shared.orphan")), lambda _m: None
        )
