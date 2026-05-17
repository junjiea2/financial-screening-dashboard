"""Serve the dashboard on a local URL."""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    port = 8765
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(  # noqa: E731
        *args,
        directory=str(root),
        **kwargs,
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Dashboard: http://127.0.0.1:{port}/dashboard/")
    server.serve_forever()


if __name__ == "__main__":
    main()

