"""Governed Workflow Definition lifecycle and DAG validation."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agent_console.workflow_definition_repository import (
    WorkflowDefinitionConflict,
    WorkflowDefinitionNotFound,
    WorkflowDefinitionRepository,
    WorkflowScope,
)


class WorkflowDefinitionFailure(RuntimeError):
    def __init__(self, reason: str, status: int = 422):
        super().__init__(reason)
        self.reason, self.status = reason, status


def _now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _id(prefix):
    return f"{prefix}:{uuid4()}"


def _digest(record, revision):
    value = {
        "schema": "workflow-definition/v1",
        "namespace": record["namespace"],
        "securityDomain": record["securityDomain"],
        "workflowDefinitionId": record["workflowDefinitionId"],
        "predecessorRevisionId": revision.get("predecessorRevisionId"),
        "content": revision["content"],
    }
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


class WorkflowDefinitionService:
    def __init__(
        self,
        repository: WorkflowDefinitionRepository,
        reference_resolver: Callable[[WorkflowScope, dict[str, Any]], bool]
        | None = None,
    ):
        self.repository, self.reference_resolver = repository, reference_resolver

    @staticmethod
    def scope(namespace, security_domain):
        return WorkflowScope(namespace, security_domain)

    def create(self, scope, actor, name, content):
        self._validate_content(scope, content, resolve=False)
        revision = {
            "revisionId": _id("workflow-revision"),
            "predecessorRevisionId": None,
            "state": "DRAFT",
            "content": copy.deepcopy(content),
            "createdAt": _now(),
        }
        record = {
            "workflowDefinitionId": _id("workflow-definition"),
            "namespace": scope.namespace,
            "securityDomain": scope.security_domain,
            "name": name.strip(),
            "aggregateVersion": 1,
            "lifecycleState": "DRAFT",
            "currentDraftRevisionId": revision["revisionId"],
            "publishedRevisionId": None,
            "revisions": [revision],
            "reviews": [],
            "relationships": [],
            "consumers": [],
            "facts": [],
            "createdAt": _now(),
            "updatedAt": _now(),
        }
        revision["digest"] = _digest(record, revision)
        record["facts"] = [self._fact("DRAFT_CREATED", actor, revision)]
        return self.repository.create(record)

    def list(self, scope):
        return [self.project(x) for x in self.repository.list(scope)]

    def get(self, scope, resource_id):
        try:
            return self.project(self.repository.get(scope, resource_id))
        except WorkflowDefinitionNotFound as exc:
            raise WorkflowDefinitionFailure(
                "WORKFLOW_DEFINITION_NOT_FOUND", 404
            ) from exc

    def edit(self, scope, resource_id, actor, expected, content):
        record = self._load(scope, resource_id)
        self._expected(record, expected)
        self._validate_content(scope, content, resolve=False)
        prior = self._draft(record)
        revision = {
            "revisionId": _id("workflow-revision"),
            "predecessorRevisionId": prior["revisionId"],
            "state": "DRAFT",
            "content": copy.deepcopy(content),
            "createdAt": _now(),
        }
        revision["digest"] = _digest(record, revision)
        record["revisions"].append(revision)
        record["currentDraftRevisionId"] = revision["revisionId"]
        return self._replace(record, expected, "DRAFT_EDITED", actor, revision)

    def validate(self, scope, resource_id, actor, expected):
        record = self._load(scope, resource_id)
        self._expected(record, expected)
        draft = self._draft(record)
        self._validate_content(scope, draft["content"], resolve=True)
        draft["state"] = "VALIDATED"
        draft["validatedAt"] = _now()
        record["lifecycleState"] = "VALIDATED"
        return self._replace(record, expected, "DRAFT_VALIDATED", actor, draft)

    def review(self, scope, resource_id, actor, expected, digest, decision, reason):
        record = self._load(scope, resource_id)
        self._expected(record, expected)
        draft = self._draft(record)
        if draft["state"] != "VALIDATED":
            raise WorkflowDefinitionFailure("VALIDATION_REQUIRED", 409)
        if digest != draft["digest"]:
            raise WorkflowDefinitionFailure("EXACT_DIGEST_REQUIRED", 409)
        if decision != "APPROVE" or not reason.strip():
            raise WorkflowDefinitionFailure("HUMAN_REVIEW_REJECTED", 409)
        review = {
            "reviewId": _id("workflow-review"),
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

    def publish(self, scope, resource_id, actor, expected, digest, review_id):
        record = self._load(scope, resource_id)
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
            raise WorkflowDefinitionFailure("EXACT_REVIEW_REQUIRED", 409)
        draft["state"] = "PUBLISHED"
        draft["publishedAt"] = _now()
        record["publishedRevisionId"] = draft["revisionId"]
        record["currentDraftRevisionId"] = None
        record["lifecycleState"] = "PUBLISHED"
        return self._replace(record, expected, "REVISION_PUBLISHED", actor, draft)

    def successor(self, scope, resource_id, actor, expected):
        record = self._load(scope, resource_id)
        self._expected(record, expected)
        if record["currentDraftRevisionId"]:
            raise WorkflowDefinitionFailure("DRAFT_ALREADY_EXISTS", 409)
        published = next(
            x
            for x in record["revisions"]
            if x["revisionId"] == record["publishedRevisionId"]
        )
        revision = {
            "revisionId": _id("workflow-revision"),
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
        ordered = []
        revision = next(
            (
                x
                for x in record["revisions"]
                if x["revisionId"]
                == (record["currentDraftRevisionId"] or record["publishedRevisionId"])
            ),
            None,
        )
        if revision:
            ordered = self._stable_order(revision["content"]["tasks"])
        return {
            "definition": copy.deepcopy(record),
            "productProjection": {
                "workflowDefinitionId": record["workflowDefinitionId"],
                "name": record["name"],
                "state": record["lifecycleState"],
                "taskCount": len(ordered),
                "orderedTaskIds": ordered,
                "relationshipCount": len(record["relationships"]),
                "consumerCount": len(record["consumers"]),
            },
            "technicalProjection": {
                "workflowDefinitionId": record["workflowDefinitionId"],
                "aggregateVersion": record["aggregateVersion"],
                "publishedRevisionId": record["publishedRevisionId"],
                "revisionDigests": [
                    {
                        "revisionId": x["revisionId"],
                        "digest": x["digest"],
                        "state": x["state"],
                    }
                    for x in record["revisions"]
                ],
                "relationships": copy.deepcopy(record["relationships"]),
                "consumers": copy.deepcopy(record["consumers"]),
            },
        }

    def compare(self, scope, resource_id, left_revision_id, right_revision_id):
        record = self._load(scope, resource_id)
        revisions = {item["revisionId"]: item for item in record["revisions"]}
        if left_revision_id not in revisions or right_revision_id not in revisions:
            raise WorkflowDefinitionFailure("WORKFLOW_REVISION_NOT_FOUND", 404)
        left, right = revisions[left_revision_id], revisions[right_revision_id]
        left_tasks = {item["taskId"]: item for item in left["content"]["tasks"]}
        right_tasks = {item["taskId"]: item for item in right["content"]["tasks"]}
        return {
            "workflowDefinitionId": resource_id,
            "leftRevisionId": left_revision_id,
            "rightRevisionId": right_revision_id,
            "addedTaskIds": sorted(right_tasks.keys() - left_tasks.keys()),
            "removedTaskIds": sorted(left_tasks.keys() - right_tasks.keys()),
            "changedTaskIds": sorted(
                key
                for key in left_tasks.keys() & right_tasks.keys()
                if left_tasks[key] != right_tasks[key]
            ),
            "digestChanged": left["digest"] != right["digest"],
        }

    def _validate_content(self, scope, content, *, resolve):
        forbidden = {
            "podYaml",
            "podName",
            "env",
            "environment",
            "exec",
            "command",
            "rawSecret",
            "secretValue",
            "logs",
        }

        def walk(value):
            if isinstance(value, dict):
                if forbidden.intersection(value):
                    raise WorkflowDefinitionFailure("UNSAFE_RUNTIME_FIELD_FORBIDDEN")
                for v in value.values():
                    walk(v)
            elif isinstance(value, list):
                for v in value:
                    walk(v)

        walk(content)
        self._stable_order(content["tasks"])
        refs = [
            content["runtimeProfile"],
            *(r for t in content["tasks"] for r in t.get("references", [])),
        ]
        if resolve:
            if self.reference_resolver is None:
                raise WorkflowDefinitionFailure("REFERENCE_RESOLVER_UNAVAILABLE", 503)
            for ref in refs:
                if not self.reference_resolver(scope, ref):
                    raise WorkflowDefinitionFailure("EXACT_REFERENCE_NOT_FOUND", 409)

    @staticmethod
    def _stable_order(tasks):
        ids = [x["taskId"] for x in tasks]
        if len(ids) != len(set(ids)):
            raise WorkflowDefinitionFailure("DUPLICATE_TASK_ID")
        known = set(ids)
        deps = {x["taskId"]: set(x.get("dependsOn", [])) for x in tasks}
        if any(not value <= known or key in value for key, value in deps.items()):
            raise WorkflowDefinitionFailure("INVALID_TASK_DEPENDENCY")
        result = []
        while deps:
            ready = sorted(k for k, v in deps.items() if not v)
            if not ready:
                raise WorkflowDefinitionFailure("WORKFLOW_CYCLE_DETECTED")
            result.extend(ready)
            for key in ready:
                deps.pop(key)
            for value in deps.values():
                value.difference_update(ready)
        return result

    def _load(self, scope, rid):
        try:
            return self.repository.get(scope, rid)
        except WorkflowDefinitionNotFound as exc:
            raise WorkflowDefinitionFailure(
                "WORKFLOW_DEFINITION_NOT_FOUND", 404
            ) from exc

    @staticmethod
    def _expected(record, expected):
        if record["aggregateVersion"] != expected:
            raise WorkflowDefinitionFailure("STALE_WORKFLOW_DEFINITION", 409)

    @staticmethod
    def _draft(record):
        rid = record["currentDraftRevisionId"]
        if not rid:
            raise WorkflowDefinitionFailure("DRAFT_NOT_FOUND", 409)
        return next(x for x in record["revisions"] if x["revisionId"] == rid)

    @staticmethod
    def _fact(event, actor, subject):
        return {
            "factId": _id("workflow-fact"),
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
        except WorkflowDefinitionConflict as exc:
            raise WorkflowDefinitionFailure("STALE_WORKFLOW_DEFINITION", 409) from exc
