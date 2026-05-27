import textwrap
from pathlib import Path

import pytest

from vested_connect.cli import main


def _write_bootstrap(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "bootstrap.py"
    p.write_text(body)
    return p


def test_cli_help_returns_nonzero(capsys) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    # argparse --help calls sys.exit(0) directly.
    assert exc.value.code == 0


def test_cli_worker_missing_bootstrap_file(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("VESTED_CONNECTOR_TOKEN", "tok")
    monkeypatch.setenv("VESTED_CONNECTOR_HUB", "h:1234")
    with pytest.raises(SystemExit) as exc:
        main(["worker", "--bootstrap", str(tmp_path / "does_not_exist.py")])
    assert exc.value.code == 1
    assert "bootstrap not found" in capsys.readouterr().err


def test_cli_worker_bootstrap_without_app_var(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    bp = _write_bootstrap(tmp_path, "# no `app` variable\n")
    monkeypatch.setenv("VESTED_CONNECTOR_TOKEN", "tok")
    monkeypatch.setenv("VESTED_CONNECTOR_HUB", "h:1234")
    with pytest.raises(SystemExit) as exc:
        main(["worker", "--bootstrap", str(bp)])
    assert exc.value.code == 1
    assert "must define `app`" in capsys.readouterr().err


def test_cli_worker_missing_token_returns_78(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    bp = _write_bootstrap(tmp_path, textwrap.dedent("""
        from vested_connect import ConnectorApp
        app = ConnectorApp.create()
    """))
    monkeypatch.delenv("VESTED_CONNECTOR_TOKEN", raising=False)
    monkeypatch.setenv("VESTED_CONNECTOR_HUB", "h:1234")
    code = main(["worker", "--bootstrap", str(bp)])
    assert code == 78
    assert "VESTED_CONNECTOR_TOKEN" in capsys.readouterr().err


def test_cli_worker_missing_hub_returns_78(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    bp = _write_bootstrap(tmp_path, textwrap.dedent("""
        from vested_connect import ConnectorApp
        app = ConnectorApp.create()
    """))
    monkeypatch.setenv("VESTED_CONNECTOR_TOKEN", "tok")
    monkeypatch.delenv("VESTED_CONNECTOR_HUB", raising=False)
    code = main(["worker", "--bootstrap", str(bp)])
    assert code == 78
    assert "VESTED_CONNECTOR_HUB" in capsys.readouterr().err
