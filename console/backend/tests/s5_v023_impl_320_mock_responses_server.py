"""Local HTTPS Kimi Responses mock owned by S5-V023-IMPL-320."""
# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    calls = 0

    def do_GET(self):
        if self.path == "/ready":
            self.send_response(204)
            self.end_headers()
            return
        if self.path != "/stats":
            self.send_error(404)
            return
        payload = json.dumps({"dispatchCount": type(self).calls}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        if self.path != "/v1/responses":
            self.send_error(404)
            return
        type(self).calls += 1
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
        forbidden = {
            "tools",
            "tool_choice",
            "parallel_tool_calls",
            "truncation",
            "previous_response_id",
        }
        if self.headers.get("authorization") != "Bearer local-kimi-mock-key-320":
            self.send_error(401)
            return
        if (
            request.get("model") != "mock-kimi-k3-320"
            or request.get("store") is not False
            or request.get("background") is not False
            or request.get("max_output_tokens") != 4096
            or request.get("reasoning") != {"effort": "low"}
            or forbidden.intersection(request)
            or request.get("text", {}).get("format", {}).get("type") != "json_schema"
            or request.get("text", {}).get("format", {}).get("strict") is not True
        ):
            self.send_error(422)
            return
        if "[DISCONNECT]" in content:
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
        response = (
            {
                "id": "resp_local_kimi_mock_320_nonterminal",
                "status": "in_progress",
                "model": "mock-kimi-k3-320",
                "output": [],
                "usage": {"input_tokens": 80, "output_tokens": 0},
            }
            if "[NONTERMINAL]" in content
            else {
                "id": "resp_local_kimi_mock_320",
                "status": "completed",
                "model": "mock-kimi-k3-320",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "output_text", "text": json.dumps(result)}
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 80,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens": 40,
                    "output_tokens_details": {"reasoning_tokens": 20},
                },
            }
        )
        payload = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.send_header("x-request-id", "req_local_kimi_mock_320")
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
