import pytest

from vested_connect import ConnectorApp


def test_create_returns_fresh_instance() -> None:
    a = ConnectorApp.create()
    b = ConnectorApp.create()
    assert a is not b
    assert a.agents == []
    assert a.tools == {}


def test_scan_module_collects_from_fixture(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # tests/fixtures is on sys.path via conftest or pyproject pytest config;
    # if it isn't, prepend it explicitly.
    import sys
    from pathlib import Path
    fixtures_dir = str(Path(__file__).parent / "fixtures")
    if fixtures_dir not in sys.path:
        sys.path.insert(0, fixtures_dir)

    app = ConnectorApp.create().scan_module("sample_app")
    assert len(app.agents) == 1
    assert app.agents[0].key == "sample.insights"
    assert "sample.insights.echo" in app.tools


def test_scan_module_rejects_duplicate_agent_key() -> None:
    import sys
    from pathlib import Path
    fixtures_dir = str(Path(__file__).parent / "fixtures")
    if fixtures_dir not in sys.path:
        sys.path.insert(0, fixtures_dir)

    app = ConnectorApp.create().scan_module("sample_app")
    with pytest.raises(RuntimeError, match="duplicate agent key"):
        app.scan_module("sample_app")


def test_with_logger_chains() -> None:
    import logging
    log = logging.getLogger("custom")
    app = ConnectorApp.create().with_logger(log)
    assert app.logger is log
