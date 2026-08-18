import pytest

from vested_connect.errors import ConnectorError
from vested_connect.tool_binding import (
    resolve_bindings,
    validate_bindings,
    validate_hub_limits,
)


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


# Learned the hard way on 2026-08-18: agents=["*"] on erp_bc's run_sql pushed
# ONE agent from 30 tools to 31, one over that connector's limit, so the hub
# rejected the whole Register — and with no declaration, BOTH the schema gate
# and the credential gate refused every call for ~1 hour.

def _bind(agent_keys: tuple[str, ...], tools: tuple[_Tool, ...]) -> dict[str, list[_Tool]]:
    return resolve_bindings([_Agent(k) for k in agent_keys], {t.key: t for t in tools})


def test_hub_limits_under_and_exactly_at_the_limit_do_not_raise() -> None:
    bound = _bind(("erp.data",), (_Tool("erp.data.a"), _Tool("erp.data.b")))
    validate_hub_limits(bound, 3)
    # The hub refuses 31 against 30, so the limit itself is allowed. Off-by-one
    # here would ground a connector the hub accepts.
    validate_hub_limits(bound, 2)


def test_hub_limits_over_the_limit_names_the_agent_and_counts() -> None:
    bound = _bind(("erp.data",), (_Tool("erp.data.a"), _Tool("erp.data.b"), _Tool("erp.data.c")))
    with pytest.raises(ConnectorError, match=r"erp\.data") as e:
        validate_hub_limits(bound, 2)
    assert "3 tools" in str(e.value)
    assert "limit is 2" in str(e.value)


def test_hub_limits_names_the_shared_tool_when_one_contributed() -> None:
    bound = _bind(
        ("erp.data", "erp.retail"),
        (_Tool("erp.retail.a"), _Tool("erp.retail.b"), _Tool("erp.shared.run_sql", ("*",))),
    )
    with pytest.raises(ConnectorError, match=r"erp\.shared\.run_sql"):
        validate_hub_limits(bound, 2)


def test_hub_limits_zero_means_unknown() -> None:
    # proto3 defaults uint32 to 0 and an older hub sends nothing; reading that
    # as a real ceiling would ground every connector — this check inverted.
    bound = _bind(("erp.data",), (_Tool("erp.data.a"), _Tool("erp.data.b")))
    validate_hub_limits(bound, 0)
