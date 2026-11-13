"""Optional local process observation after the original Native READ checks.

This is never execution state or authority; unreadable/old evidence stays unknown.
"""

import hashlib
import json
import os
import stat
import time
from datetime import UTC, datetime
from pathlib import Path

from psycopg import Error as PostgresError


def process_projection(call, preparation):
    directory = os.environ.get("NATIVE_EXACT_HOST_SERVICE_STATUS_DIRECTORY")
    if not directory:
        return None
    unknown = {
        "state": "UNKNOWN",
        "preparationDigest": preparation.digest,
        "runId": preparation.run_id,
        "observedAt": None,
        "reasonCode": "OBSERVATION_UNAVAILABLE",
    }
    try:
        # Requester READ was checked by records(). The view belongs to the unique
        # execution subject, which can differ from this authorized reader.
        with call.connection.transaction():
            subjects = call.connection.execute(
                "SELECT DISTINCT n.principal_id FROM "
                "execution_authority.native_dispatch_commands n "
                "JOIN execution_authority.attempts a "
                "USING(namespace,security_domain,attempt_id) "
                "JOIN execution_authority.prepared_task_bindings b "
                "USING(namespace,security_domain,task_run_id) "
                "WHERE b.namespace=%s AND b.security_domain=%s "
                "AND b.workflow_run_id=%s AND n.authorization_resource=%s LIMIT 2",
                (
                    preparation.namespace,
                    preparation.security_domain,
                    preparation.run_id,
                    "governed-execution:prepared:" + preparation.digest,
                ),
            ).fetchall()
        if (
            len(subjects) != 1
            or not isinstance(subjects[0]["principal_id"], str)
            or not subjects[0]["principal_id"]
        ):
            return unknown
        identity = [
            preparation.namespace,
            preparation.security_domain,
            subjects[0]["principal_id"],
            preparation.digest,
        ]
        key = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        root = Path(directory)
        if not root.is_absolute() or root.resolve() != root:
            return unknown
        info = root.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            return unknown
        fd = os.open(
            root / ("view-" + key + ".json"),
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
        )
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > 4096
            ):
                return unknown
            value = json.load(stream)
        if (
            value.get("schema") != "native-exact-host-view.v1"
            or value.get("identity") != identity
            or value.get("runId") != preparation.run_id
        ):
            return unknown
        observed, ttl = value["observedAt"], value["validForSeconds"]
        if (
            type(observed) not in (int, float)
            or type(ttl) is not int
            or not 1 <= ttl <= 180
            or not 0 <= time.time() - observed <= ttl
        ):
            return unknown
        states = {"QUEUED", "STARTING", "READY", "STOPPING", "BLOCKED", "UNKNOWN"}
        reasons = {
            None,
            "WAITING_CAPACITY",
            "START_BLOCKED",
            "CURRENT_CONDITIONS_BLOCKED",
            "OBSERVATION_UNAVAILABLE",
        }
        if value.get("state") not in states or value.get("reasonCode") not in reasons:
            return unknown
        return {
            **unknown,
            "state": value["state"],
            "reasonCode": value["reasonCode"],
            "observedAt": datetime.fromtimestamp(observed, UTC).isoformat(),
        }
    except (OSError, ValueError, TypeError, KeyError, OverflowError, PostgresError):
        return unknown
