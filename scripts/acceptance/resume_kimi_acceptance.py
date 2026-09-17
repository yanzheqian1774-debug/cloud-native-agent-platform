#!/usr/bin/env python3
"""Start only the reviewed, preserved original acceptance assets."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for part in (
    "core/src",
    "gateway/src",
    "operator/src",
    "runtime/src",
    "console/backend/src",
):
    sys.path.insert(0, str(ROOT / part))

from agent_console.acceptance_recovery import RecoveryError, serve  # noqa: E402
from agent_console.authority_contracts import AuthorityError  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--restricted-create", action="store_true")
    args = parser.parse_args()
    try:
        serve(
            args.manifest,
            args.manifest_sha256,
            restricted_create=args.restricted_create,
        )
    except (RecoveryError, AuthorityError) as exc:
        reason = exc.reason_code if isinstance(exc, AuthorityError) else str(exc)
        print(f"RECOVERY_REFUSED:{reason}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as exc:
        # Database/SSL/JSON exceptions may contain connection or identity material.
        print(f"RECOVERY_REFUSED:{type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
