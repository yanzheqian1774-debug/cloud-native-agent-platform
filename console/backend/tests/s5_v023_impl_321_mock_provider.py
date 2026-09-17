"""Deterministic HTTPS wire fixture, never a semantic quality oracle."""

from __future__ import annotations

import argparse
import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agent_console.draft_assistance_policy import FIELDS, V2_SCHEMA_VERSION, policy_for


class Handler(BaseHTTPRequestHandler):
    calls = 0

    def log_message(self, *args):
        pass

    def do_GET(self):
        payload = json.dumps(
            {"calls": type(self).calls, "quality": "NOT_MEASURED"}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["content-length"])))
        policy = policy_for("v2", V2_SCHEMA_VERSION)
        if (
            self.path != "/v1/responses"
            or self.headers.get("authorization") != "Bearer local-mock-key-321"
            or request["instructions"] != policy.instructions
            or request["text"]["format"]["schema"] != policy.schema
        ):
            self.send_error(422)
            return
        context = json.loads(request["input"][0]["content"][0]["text"])
        type(self).calls += 1
        # Explicit test protocol: echo only a user-authored full fixture field.
        # This is transport/authorization testing, not model understanding.
        text = context["messages"][-1]["text"]
        refs = [context["messages"][-1]["id"]]
        result = {
            "kind": "DRAFT_READY",
            "title": "321隔离验收",
            "description": text,
            "clarificationQuestion": None,
            "questions": [],
            "understanding": [
                {
                    "field": field,
                    "value": text[:200] if field == "goal" else "尚不清楚",
                    "source": "USER_STATEMENT" if field == "goal" else "UNKNOWN",
                    "sourceRefs": refs if field == "goal" else [],
                }
                for field in FIELDS[:-1]
            ],
        }
        payload = json.dumps(
            {
                "id": f"resp_321_{type(self).calls}",
                "status": "completed",
                "model": "mock-model-321",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(result, ensure_ascii=False),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 500, "output_tokens": 300},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", 19323), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(args.runtime_dir / "cert.pem", args.runtime_dir / "key.pem")
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
