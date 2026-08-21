"""Provider-specific experiment wiring; the generic caller stays native-free."""

from __future__ import annotations

import json
import os
import sys

from generic_caller import execute
from openclaw_provider import OpenClawBinding, OpenClawProvider


def main() -> int:
    provider = OpenClawProvider(
        cli=(os.environ["OPENCLAW_NODE"], os.environ["OPENCLAW_ENTRYPOINT"]),
        binding=OpenClawBinding(
            gateway_url=os.environ["OPENCLAW_GATEWAY_URL"],
            agent_id=os.environ.get("OPENCLAW_AGENT_ID", "main"),
            session_key=os.environ.get(
                "OPENCLAW_SESSION_KEY", "agent:main:s5-spike-002-checkpoint-b"
            ),
        ),
        token_env="OPENCLAW_GATEWAY_TOKEN",
        environment={
            "OPENCLAW_STATE_DIR": os.environ["OPENCLAW_STATE_DIR"],
            "OPENCLAW_CONFIG_PATH": os.environ["OPENCLAW_CONFIG_PATH"],
        },
    )
    observations = provider.observe()
    if "--observe-only" in sys.argv[1:]:
        print(
            json.dumps(
                {
                    "observations": [
                        {
                            "name": item.name,
                            "value": item.value.value,
                            "reason": item.reason,
                        }
                        for item in observations
                    ]
                },
                indent=2,
            )
        )
        return 0
    outcome = execute(provider, "Checkpoint B real Provider interaction.")
    print(
        json.dumps(
            {
                "observations": [
                    {
                        "name": item.name,
                        "value": item.value.value,
                        "reason": item.reason,
                    }
                    for item in observations
                ],
                "outcome": {
                    "kind": outcome.kind.value,
                    "correlationId": outcome.correlation_id,
                    "message": outcome.message,
                    "observedAtMs": outcome.observed_at_ms,
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
