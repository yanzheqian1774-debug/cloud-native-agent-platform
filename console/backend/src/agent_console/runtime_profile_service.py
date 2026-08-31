"""Governed, declarative-only Runtime Profile lifecycle."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import UTC, datetime
from uuid import uuid4

from agent_console.runtime_profile_repository import (
    RuntimeProfileConflict,
    RuntimeProfileNotFound,
    RuntimeProfileRepository,
    RuntimeProfileScope,
)


class RuntimeProfileFailure(RuntimeError):
    def __init__(self, reason: str, status: int = 422):
        super().__init__(reason)
        self.reason, self.status = reason, status


def _now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _id(prefix):
    return f"{prefix}:{uuid4()}"


def _digest(record, revision):
    value = {
        "schema": "runtime-profile/v1",
        "namespace": record["namespace"],
        "securityDomain": record["securityDomain"],
        "runtimeProfileId": record["runtimeProfileId"],
        "predecessorRevisionId": revision.get("predecessorRevisionId"),
        "content": revision["content"],
    }
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


class RuntimeProfileService:
    def __init__(self, repository: RuntimeProfileRepository):
        self.repository = repository

    @staticmethod
    def scope(namespace, security_domain):
        return RuntimeProfileScope(namespace, security_domain)

    def create(self, scope, actor, name, content):
        self._validate(content)
        revision = {
            "revisionId": _id("runtime-profile-revision"),
            "predecessorRevisionId": None,
            "state": "DRAFT",
            "content": copy.deepcopy(content),
            "createdAt": _now(),
        }
        record = {
            "runtimeProfileId": _id("runtime-profile"),
            "namespace": scope.namespace,
            "securityDomain": scope.security_domain,
            "name": name.strip(),
            "aggregateVersion": 1,
            "lifecycleState": "DRAFT",
            "currentDraftRevisionId": revision["revisionId"],
            "publishedRevisionId": None,
            "revisions": [revision],
            "reviews": [],
            "facts": [],
            "createdAt": _now(),
            "updatedAt": _now(),
        }
        revision["digest"] = _digest(record, revision)
        record["facts"] = [self._fact("DRAFT_CREATED", actor, revision)]
        return self.repository.create(record)

    def list(self, scope):
        return [self.project(x) for x in self.repository.list(scope)]

    def get(self, scope, rid):
        try:
            return self.project(self.repository.get(scope, rid))
        except RuntimeProfileNotFound as exc:
            raise RuntimeProfileFailure("RUNTIME_PROFILE_NOT_FOUND", 404) from exc

    def edit(self, scope, rid, actor, expected, content):
        record = self._load(scope, rid)
        self._expected(record, expected)
        self._validate(content)
        prior = self._draft(record)
        revision = {
            "revisionId": _id("runtime-profile-revision"),
            "predecessorRevisionId": prior["revisionId"],
            "state": "DRAFT",
            "content": copy.deepcopy(content),
            "createdAt": _now(),
        }
        revision["digest"] = _digest(record, revision)
        record["revisions"].append(revision)
        record["currentDraftRevisionId"] = revision["revisionId"]
        return self._replace(record, expected, "DRAFT_EDITED", actor, revision)

    def validate(self, scope, rid, actor, expected):
        record = self._load(scope, rid)
        self._expected(record, expected)
        draft = self._draft(record)
        self._validate(draft["content"])
        draft["state"] = "VALIDATED"
        draft["validatedAt"] = _now()
        record["lifecycleState"] = "VALIDATED"
        return self._replace(record, expected, "DRAFT_VALIDATED", actor, draft)

    def review(self, scope, rid, actor, expected, digest, decision, reason):
        record = self._load(scope, rid)
        self._expected(record, expected)
        draft = self._draft(record)
        if draft["state"] != "VALIDATED":
            raise RuntimeProfileFailure("VALIDATION_REQUIRED", 409)
        if digest != draft["digest"]:
            raise RuntimeProfileFailure("EXACT_DIGEST_REQUIRED", 409)
        if decision != "APPROVE" or not reason.strip():
            raise RuntimeProfileFailure("HUMAN_REVIEW_REJECTED", 409)
        review = {
            "reviewId": _id("runtime-profile-review"),
            "revisionId": draft["revisionId"],
            "digest": digest,
            "decision": "APPROVED",
            "actor": actor,
            "reason": reason.strip(),
            "reviewedAt": _now(),
        }
        record["reviews"].append(review)
        draft["state"] = "HUMAN_REVIEWED"
        record["lifecycleState"] = "HUMAN_REVIEWED"
        return self._replace(record, expected, "HUMAN_REVIEWED", actor, review)

    def publish(self, scope, rid, actor, expected, digest, review_id):
        record = self._load(scope, rid)
        self._expected(record, expected)
        draft = self._draft(record)
        review = next(
            (x for x in record["reviews"] if x["reviewId"] == review_id), None
        )
        if (
            not review
            or review["digest"] != digest
            or draft["digest"] != digest
            or draft["state"] != "HUMAN_REVIEWED"
        ):
            raise RuntimeProfileFailure("EXACT_REVIEW_REQUIRED", 409)
        draft["state"] = "PUBLISHED"
        draft["publishedAt"] = _now()
        record["publishedRevisionId"] = draft["revisionId"]
        record["currentDraftRevisionId"] = None
        record["lifecycleState"] = "PUBLISHED"
        return self._replace(record, expected, "REVISION_PUBLISHED", actor, draft)

    def successor(self, scope, rid, actor, expected):
        record = self._load(scope, rid)
        self._expected(record, expected)
        if record["currentDraftRevisionId"]:
            raise RuntimeProfileFailure("DRAFT_ALREADY_EXISTS", 409)
        published = next(
            x
            for x in record["revisions"]
            if x["revisionId"] == record["publishedRevisionId"]
        )
        revision = {
            "revisionId": _id("runtime-profile-revision"),
            "predecessorRevisionId": published["revisionId"],
            "state": "DRAFT",
            "content": copy.deepcopy(published["content"]),
            "createdAt": _now(),
        }
        revision["digest"] = _digest(record, revision)
        record["revisions"].append(revision)
        record["currentDraftRevisionId"] = revision["revisionId"]
        record["lifecycleState"] = "DRAFT"
        return self._replace(record, expected, "SUCCESSOR_CREATED", actor, revision)

    def project(self, record):
        active = next(
            (
                x
                for x in record["revisions"]
                if x["revisionId"]
                == (record["currentDraftRevisionId"] or record["publishedRevisionId"])
            ),
            None,
        )
        content = active["content"] if active else {}
        return {
            "profile": copy.deepcopy(record),
            "productProjection": {
                "runtimeProfileId": record["runtimeProfileId"],
                "name": record["name"],
                "state": record["lifecycleState"],
                "provider": content.get("provider"),
            },
            "technicalProjection": {
                "runtimeProfileId": record["runtimeProfileId"],
                "aggregateVersion": record["aggregateVersion"],
                "publishedRevisionId": record["publishedRevisionId"],
                "resources": content.get("resources"),
                "isolation": content.get("isolation"),
                "stateMode": content.get("stateMode"),
                "sessionAffinity": content.get("sessionAffinity"),
                "revisionDigests": [
                    {
                        "revisionId": x["revisionId"],
                        "digest": x["digest"],
                        "state": x["state"],
                    }
                    for x in record["revisions"]
                ],
                "executionAuthority": False,
            },
        }

    @staticmethod
    def _validate(content):
        raw = json.dumps(content).lower()
        forbidden = (
            "podyaml",
            "podname",
            "secretvalue",
            "rawsecret",
            "environment",
            '"env"',
            '"exec"',
            '"command"',
            "unsanitizedlog",
        )
        if any(x in raw for x in forbidden):
            raise RuntimeProfileFailure("UNSAFE_RUNTIME_FIELD_FORBIDDEN")
        resources = content["resources"]

        def cpu(x):
            return int(x[:-1])

        def mem(x):
            match = re.fullmatch(r"([1-9][0-9]*)(Mi|Gi)", x)
            if not match:
                raise RuntimeProfileFailure("RESOURCE_QUANTITY_INVALID")
            return int(match.group(1)) * (1024 if match.group(2) == "Gi" else 1)

        if cpu(resources["cpuRequest"]) > cpu(resources["cpuLimit"]) or mem(
            resources["memoryRequest"]
        ) > mem(resources["memoryLimit"]):
            raise RuntimeProfileFailure("RESOURCE_REQUEST_EXCEEDS_LIMIT")
        if content["provider"] == "OPENCLAW" and not content.get("openClawPackageRef"):
            raise RuntimeProfileFailure("OPENCLAW_PACKAGE_REFERENCE_REQUIRED")
        if content["provider"] == "NATIVE_KUBERNETES" and content.get(
            "openClawPackageRef"
        ):
            raise RuntimeProfileFailure("OPENCLAW_FIELD_FORBIDDEN")
        if any(
            not x.startswith("secret-ref:") for x in content.get("secretReferences", [])
        ):
            raise RuntimeProfileFailure("TYPED_SECRET_REFERENCE_REQUIRED")

    def _load(self, scope, rid):
        try:
            return self.repository.get(scope, rid)
        except RuntimeProfileNotFound as exc:
            raise RuntimeProfileFailure("RUNTIME_PROFILE_NOT_FOUND", 404) from exc

    @staticmethod
    def _expected(record, expected):
        if record["aggregateVersion"] != expected:
            raise RuntimeProfileFailure("STALE_RUNTIME_PROFILE", 409)

    @staticmethod
    def _draft(record):
        rid = record["currentDraftRevisionId"]
        if not rid:
            raise RuntimeProfileFailure("DRAFT_NOT_FOUND", 409)
        return next(x for x in record["revisions"] if x["revisionId"] == rid)

    @staticmethod
    def _fact(event, actor, subject):
        return {
            "factId": _id("runtime-profile-fact"),
            "event": event,
            "actor": actor,
            "recordedAt": _now(),
            "subject": copy.deepcopy(subject),
        }

    def _replace(self, record, expected, event, actor, subject):
        fact = self._fact(event, actor, subject)
        record["aggregateVersion"] = expected + 1
        record["updatedAt"] = _now()
        try:
            return self.repository.replace(record, expected_version=expected, fact=fact)
        except RuntimeProfileConflict as exc:
            raise RuntimeProfileFailure("STALE_RUNTIME_PROFILE", 409) from exc
