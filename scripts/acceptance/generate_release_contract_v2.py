#!/usr/bin/env python3
"""Generate a validated schema-v2 instance from one explicit JSON input."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from release_contract_v2 import (
    atomic_write,
    jcs_bytes,
    load_json_exact,
    pairing_digest,
    validate_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seal-directory", action="store_true")
    args = parser.parse_args()
    value = load_json_exact(args.input.read_bytes())
    product = value.get("productProvenance")
    tool = value.get("acceptanceToolProvenance")
    if isinstance(product, dict) and isinstance(tool, dict):
        value.setdefault("approvedPairing", {})["pairingDigest"] = pairing_digest(
            product, tool
        )
    validate_contract(value)
    data = jcs_bytes(value) + b"\n"
    digest = atomic_write(args.output, data, seal_directory=args.seal_directory)
    print(json.dumps({"contractInstanceSha256": digest}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
