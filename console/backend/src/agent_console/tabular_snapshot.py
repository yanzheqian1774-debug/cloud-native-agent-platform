"""Bounded CSV materialization with explicit source bytes and column mapping."""

import csv
import hashlib
import io

from .resource_use_domain import canonical_digest


class SnapshotInputError(ValueError):
    pass


def read_csv_snapshot(
    raw: bytes,
    *,
    source_id: str,
    columns: dict[str, str],
    required: tuple[str, ...],
    max_rows: int = 10000,
):
    if (
        not isinstance(raw, bytes)
        or not isinstance(source_id, str)
        or not source_id.strip()
        or len(source_id) > 200
        or type(max_rows) is not int
        or not 1 <= max_rows <= 10000
        or len(raw) > 4 * 1024 * 1024
    ):
        raise SnapshotInputError("SNAPSHOT_BOUNDS_INVALID")
    if (
        not isinstance(columns, dict)
        or not columns
        or not all(
            isinstance(k, str) and k and isinstance(v, str) and v
            for k, v in columns.items()
        )
        or not set(required) <= columns.keys()
        or len(set(columns.values())) != len(columns)
    ):
        raise SnapshotInputError("SNAPSHOT_MAPPING_INVALID")
    try:
        text = raw.decode("utf-8-sig", errors="strict")
        if "\x00" in text:
            raise ValueError
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        headers = next(reader)
        if (
            not headers
            or len(set(headers)) != len(headers)
            or not set(columns.values()) <= set(headers)
        ):
            raise SnapshotInputError("SNAPSHOT_HEADERS_INVALID")
        indices = {k: headers.index(v) for k, v in columns.items()}
        rows = []
        for row in reader:
            if not row:
                continue
            if len(row) != len(headers):
                raise SnapshotInputError("SNAPSHOT_ROW_WIDTH_INVALID")
            if len(rows) >= max_rows:
                raise SnapshotInputError("SNAPSHOT_ROW_LIMIT")
            rows.append(
                {
                    "sourceLine": reader.line_num,
                    "values": {k: row[i] for k, i in indices.items()},
                }
            )
        if not rows:
            raise SnapshotInputError("SNAPSHOT_EMPTY")
    except SnapshotInputError:
        raise
    except (UnicodeError, csv.Error, StopIteration, ValueError) as exc:
        raise SnapshotInputError("SNAPSHOT_CSV_INVALID") from exc
    document = {
        "schemaVersion": "tabular-snapshot.v1",
        "sourceId": source_id,
        "sourceBytesSha256": hashlib.sha256(raw).hexdigest(),
        "format": "CSV_UTF8",
        "columnMapping": dict(columns),
        "rows": rows,
    }
    return {**document, "snapshotDigest": canonical_digest(document)}


def verify_snapshot(snapshot):
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("schemaVersion") != "tabular-snapshot.v1"
    ):
        raise SnapshotInputError("SNAPSHOT_CONTRACT_INVALID")
    body = {k: v for k, v in snapshot.items() if k != "snapshotDigest"}
    if snapshot.get("snapshotDigest") != canonical_digest(body):
        raise SnapshotInputError("SNAPSHOT_DIGEST_MISMATCH")
    return snapshot
