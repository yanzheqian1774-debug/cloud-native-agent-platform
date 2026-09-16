"""Local HTTPS OpenAI Responses-shaped server for S5-V023-IMPL-319 acceptance."""
# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/ready":
            self.send_error(404)
            return
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        if self.path != "/v1/responses":
            self.send_error(404)
            return
        size = int(self.headers.get("content-length", "0"))
        if size < 1 or size > 64_000:
            self.send_error(400)
            return
        try:
            request = json.loads(self.rfile.read(size))
            content = request["input"][0]["content"][0]["text"]
        except (IndexError, KeyError, TypeError, json.JSONDecodeError):
            self.send_error(400)
            return
        if self.headers.get("authorization") != "Bearer local-mock-key-319":
            self.send_error(401)
            return
        if (
            request.get("model") != "mock-model-319"
            or request.get("store") is not False
            or request.get("background") is not False
            or request.get("tools") != []
            or "previous_response_id" in request
            or request.get("text", {}).get("format", {}).get("strict") is not True
        ):
            self.send_error(422)
            return
        if "[UNKNOWN]" in content:
            self.connection.shutdown(2)
            self.connection.close()
            return
        result = (
            {
                "kind": "NEEDS_CLARIFICATION",
                "clarificationQuestion": "请补充期望结果和判断完成的标准。",
                "title": None,
                "description": None,
            }
            if "用户补充：" not in content
            else {
                "kind": "DRAFT_READY",
                "clarificationQuestion": None,
                "title": "供应商来料质量改善",
                "description": content,
            }
        )
        response = {
            "id": "resp_local_mock_319",
            "status": "completed",
            "model": "mock-model-319",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": json.dumps(result)}],
                }
            ],
            "usage": {"input_tokens": 80, "output_tokens": 40},
        }
        payload = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.send_header("x-request-id", "req_local_mock_319")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format, *_args):
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.cert, args.key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
