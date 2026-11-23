"""Command line entry point: ``rolecard [--data-dir PATH] [--port N] [--no-browser]``."""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser
from collections.abc import Callable, Sequence

from rolecard import DEFAULT_PORT, __version__, create_app
from rolecard.config import ConfigError, resolve_data_dir
from rolecard.db import MigrationError

HOST = "127.0.0.1"
PORT_TRIES = 50


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rolecard", description="Local, private job-search assistant."
    )
    parser.add_argument("--data-dir", help="folder for your data (default: ~/.rolecard)")
    parser.add_argument(
        "--port", type=int, help=f"port (default: {DEFAULT_PORT} or the next free one)"
    )
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--version", action="version", version=f"rolecard {__version__}")
    return parser


def port_is_free(port: int, host: str = HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def choose_port(requested: int | None, is_free: Callable[[int], bool] = port_is_free) -> int:
    """The requested port if free, else the first free one from DEFAULT_PORT."""
    if requested is not None:
        if not 1 <= requested <= 65535:
            raise ConfigError(f"port {requested} is out of range (1-65535)")
        if not is_free(requested):
            raise ConfigError(f"port {requested} is already in use; choose another with --port")
        return requested
    for port in range(DEFAULT_PORT, DEFAULT_PORT + PORT_TRIES):
        if is_free(port):
            return port
    raise ConfigError(f"no free port between {DEFAULT_PORT} and {DEFAULT_PORT + PORT_TRIES - 1}")


def _open_browser_soon(url: str) -> None:  # pragma: no cover - opens a real browser
    threading.Timer(1.0, webbrowser.open, args=(url,)).start()


def _serve(app, port: int) -> None:  # pragma: no cover - real server
    from waitress import serve

    serve(app, host=HOST, port=port, threads=8, ident="rolecard")


def main(
    argv: Sequence[str] | None = None,
    *,
    serve: Callable = _serve,
    open_browser: Callable[[str], object] = _open_browser_soon,
    is_free: Callable[[int], bool] = port_is_free,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        data_dir = resolve_data_dir(args.data_dir)
        port = choose_port(args.port, is_free)
        app = create_app(data_dir, port=port)
    except (ConfigError, MigrationError) as exc:
        print(f"rolecard: {exc}", file=sys.stderr)
        return 2
    url = f"http://{HOST}:{port}/"
    print(f"rolecard {__version__} on {url} (data: {data_dir}). Press Ctrl+C to stop.")
    if not args.no_browser:
        open_browser(url)
    try:
        serve(app, port)
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        print(f"rolecard: cannot listen on {url}: {exc.strerror or exc}", file=sys.stderr)
        return 2
    return 0
