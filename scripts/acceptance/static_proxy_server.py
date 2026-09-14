#!/usr/bin/env python3
"""Serve built frontend files and proxy backend routes without source writes."""

from __future__ import annotations

import argparse
import http.client
import mimetypes
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


class Handler(BaseHTTPRequestHandler):
    root: Path
    backend_host: str
    backend_port: int
    forwarded_origin: str | None = None
    preserve_host = False

    def proxy(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length) if length else None
        excluded_headers = {"content-length", "connection"}
        if not self.preserve_host:
            excluded_headers.add("host")
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in excluded_headers
        }
        if self.forwarded_origin and self.command in {"POST", "PUT", "PATCH", "DELETE"}:
            headers["Origin"] = self.forwarded_origin
            headers["Sec-Fetch-Site"] = "same-origin"
        connection = http.client.HTTPConnection(self.backend_host, self.backend_port)
        connection.request(self.command, self.path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        self.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() not in {"content-length", "connection", "transfer-encoding"}:
                self.send_header(key, value)
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        connection.close()

    def static(self) -> None:
        requested = self.path.split("?", 1)[0]
        relative = requested.lstrip("/") or "index.html"
        candidate = (self.root / relative).resolve()
        if self.root not in candidate.parents or not candidate.is_file():
            candidate = self.root / "index.html"
        payload = candidate.read_bytes()
        self.send_response(200)
        self.send_header(
            "content-type",
            mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
        )
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def dispatch(self) -> None:
        if self.path == "/healthz" or self.path.startswith("/api/"):
            self.proxy()
        elif self.command == "GET":
            self.static()
        else:
            self.send_error(405)

    do_GET = dispatch
    do_POST = dispatch
    do_PUT = dispatch
    do_PATCH = dispatch
    do_DELETE = dispatch

    def log_message(self, format: str, *args: object) -> None:
        """Keep request paths and query values out of acceptance output."""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--backend-url", required=True)
    parser.add_argument("--forward-origin")
    parser.add_argument("--preserve-host", action="store_true")
    parser.add_argument("--tls-cert", type=Path)
    parser.add_argument("--tls-key", type=Path)
    args = parser.parse_args()
    backend = urlparse(args.backend_url)
    if backend.scheme != "http" or not backend.hostname or not backend.port:
        parser.error("backend URL must include explicit http host and port")
    if args.forward_origin:
        origin = urlparse(args.forward_origin)
        if (
            origin.scheme != "https"
            or not origin.hostname
            or origin.path not in {"", "/"}
            or origin.params
            or origin.query
            or origin.fragment
        ):
            parser.error("forward origin must be an HTTPS origin without a path")
        Handler.forwarded_origin = args.forward_origin.rstrip("/")
    if (args.tls_cert is None) != (args.tls_key is None):
        parser.error("TLS certificate and key must be provided together")
    Handler.root = args.root.resolve()
    Handler.backend_host = backend.hostname
    Handler.backend_port = backend.port
    Handler.preserve_host = args.preserve_host
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    if args.tls_cert is not None and args.tls_key is not None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.tls_cert, args.tls_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
