"""vested-connect CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import logging
import os
import sys
from pathlib import Path

from .app import ConnectorApp


def _load_bootstrap(path: str) -> ConnectorApp:
    """Load a bootstrap.py file. It must define `app = ConnectorApp.create()...`."""
    resolved = Path(path).resolve()
    if not resolved.is_file():
        print(f"bootstrap not found: {resolved}", file=sys.stderr)
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("bootstrap", resolved)
    if spec is None or spec.loader is None:
        print(f"could not load bootstrap from {resolved}", file=sys.stderr)
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    sys.modules["bootstrap"] = module
    spec.loader.exec_module(module)
    app = getattr(module, "app", None)
    if not isinstance(app, ConnectorApp):
        print(
            f"bootstrap {resolved} must define `app` as a ConnectorApp instance",
            file=sys.stderr,
        )
        sys.exit(1)
    return app


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vested-connect",
        description="Vested AI Connector SDK — Python.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("worker", help="Run the connector worker daemon.")
    w.add_argument(
        "--bootstrap",
        required=True,
        help="Path to bootstrap.py that defines `app = ConnectorApp.create()...`.",
    )
    w.add_argument(
        "--hub-addr",
        default=os.environ.get("VESTED_CONNECTOR_HUB", ""),
        help="Hub host:port. Defaults to $VESTED_CONNECTOR_HUB.",
    )
    w.add_argument(
        "--insecure",
        action="store_true",
        help="Use plaintext gRPC (local dev only).",
    )
    w.add_argument(
        "--token-stdin",
        action="store_true",
        help="Read the token from stdin instead of $VESTED_CONNECTOR_TOKEN.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.cmd == "worker":
        return _run_worker(args)

    parser.print_help()
    return 1


def _run_worker(args: argparse.Namespace) -> int:
    app = _load_bootstrap(args.bootstrap)

    token: str
    if args.token_stdin:
        token = sys.stdin.read().strip()
    else:
        token = os.environ.get("VESTED_CONNECTOR_TOKEN", "")
    if not token:
        print(
            "VESTED_CONNECTOR_TOKEN env (or --token-stdin) required",
            file=sys.stderr,
        )
        return 78

    hub = args.hub_addr or os.environ.get("VESTED_CONNECTOR_HUB", "")
    if not hub:
        print(
            "VESTED_CONNECTOR_HUB env (or --hub-addr) required",
            file=sys.stderr,
        )
        return 78

    return asyncio.run(app.run(token, hub, insecure=args.insecure))


if __name__ == "__main__":
    sys.exit(main())
