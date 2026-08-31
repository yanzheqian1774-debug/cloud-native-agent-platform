"""Agent Definition lifecycle authority for the first v0.2.2 vertical slice."""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from agent_console.agent_binding_validation import (
    BindingResolver,
    BindingValidationFailure,
    validate_bindings,
)
from agent_console.agent_definition_repository import (
    AgentDefinitionConflict,
    AgentDefinitionNotFound,
    AgentDefinitionRepository,
    DefinitionScope,
)
from agent_console.definition_authority import RoleDescriptor, canonical_digest


class AgentDefinitionFailure(RuntimeError):
    def __init__(self, reason: str, status: int = 422) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4()}"


def _content(value: dict[str, Any]) -> dict[str, Any]:
    try:
        role = RoleDescriptor.create(
            title=value.get("title"),
            duties=value.get("duties", []),
            data=value.get("data", []),
            knowledge=value.get("knowledge", []),
            skills=value.get("skills", []),
            capabilities=value.get("capabilities", []),
            runtimes=value.get("runtimes", []),
        )
    except ValueError as exc:
        raise AgentDefinitionFailure(str(exc)) from exc
    if not role.capabilities:
        raise AgentDefinitionFailure("CAPABILITY_REQUIRED")
    bindings = copy.deepcopy(value.get("bindings", {}))
    bindings.setdefault("skills", [])
    bindings.setdefault("mcpTools", [])
    bindings.setdefault("knowledge", [])
    return {
        "title": role.title,
        "duties": list(role.duties),
        "data": list(role.data),
        "knowledge": list(role.knowledge),
        "skills": list(role.skills),
        "capabilities": list(role.capabilities),
        "runtimes": list(role.runtimes),
        "businessPurpose": str(value.get("businessPurpose", "")).strip(),
        "bindings": bindings,
    }


def _revision_digest(record: dict[str, Any], revision: dict[str, Any]) -> str:
    return canonical_digest(
        {
            "definitionId": record["definitionId"],
            "revisionId": revision["revisionId"],
            "predecessorRevisionId": revision.get("predecessorRevisionId"),
            "namespace": record["namespace"],
            "securityDomain": record["securityDomain"],
            "content": revision["content"],
            "schemaVersion": "agent-definition-revision.v1",
        },
        domain="agent-definition-lifecycle-v1",
    )


class AgentDefinitionService:
    def __init__(
        self,
        repository: AgentDefinitionRepository,
        binding_resolver: BindingResolver | None = None,
    ) -> None:
        self.repository = repository
        self.binding_resolver = binding_resolver
        self.repository.compatibility()

    @staticmethod
    def scope(namespace: str, security_domain: str) -> DefinitionScope:
        if not namespace or not security_domain:
            raise AgentDefinitionFailure("TRUSTED_SCOPE_REQUIRED", 403)
        return DefinitionScope(namespace, security_domain)

    def create(
        self, scope: DefinitionScope, actor: str, name: str, content: dict[str, Any]
    ) -> dict[str, Any]:
        now = _now()
        record: dict[str, Any] = {
            "definitionId": _id("agent-definition"),
            "name": name.strip(),
            "namespace": scope.namespace,
            "securityDomain": scope.security_domain,
            "aggregateVersion": 1,
            "lifecycleState": "DRAFT",
            "enabled": True,
            "archived": False,
            "currentDraftRevisionId": _id("agent-revision"),
            "publishedRevisionId": None,
            "revisions": [],
            "reviews": [],
            "facts": [],
            "relationships": [],
            "createdAt": now,
            "updatedAt": now,
            "limitations": ["NO_EXECUTION_AUTHORITY", "SINGLE_NODE_POSTGRESQL"],
        }
        if not record["name"]:
            raise AgentDefinitionFailure("NAME_REQUIRED")
        revision = {
            "revisionId": record["currentDraftRevisionId"],
            "predecessorRevisionId": None,
            "state": "DRAFT",
            "content": _content(content),
            "createdAt": now,
        }
        revision["digest"] = _revision_digest(record, revision)
        record["revisions"].append(revision)
        record["facts"].append(self._fact("DRAFT_CREATED", actor, revision))
        try:
            return self.repository.create(record)
        except AgentDefinitionConflict as exc:
            raise AgentDefinitionFailure(str(exc), 409) from exc

    def list(self, scope: DefinitionScope) -> list[dict[str, Any]]:
        return [
            self.project(item)["definition"] for item in self.repository.list(scope)
        ]

    def get(self, scope: DefinitionScope, definition_id: str) -> dict[str, Any]:
        try:
            return self.project(self.repository.get(scope, definition_id))
        except AgentDefinitionNotFound as exc:
            raise AgentDefinitionFailure("AGENT_DEFINITION_NOT_FOUND", 404) from exc

    def edit(
        self,
        scope: DefinitionScope,
        definition_id: str,
        actor: str,
        expected_version: int,
        content: dict[str, Any],
    ) -> dict[str, Any]:
        record = self._load(scope, definition_id)
        self._expected(record, expected_version)
        predecessor = self._draft(record)
        revision = {
            "revisionId": _id("agent-revision"),
            "predecessorRevisionId": predecessor["revisionId"],
            "state": "DRAFT",
            "content": _content(content),
            "createdAt": _now(),
        }
        revision["digest"] = _revision_digest(record, revision)
        record["revisions"].append(revision)
        record["currentDraftRevisionId"] = revision["revisionId"]
        record["lifecycleState"] = "DRAFT"
        return self._replace(record, expected_version, "DRAFT_EDITED", actor, revision)

    def validate(
        self, scope: DefinitionScope, definition_id: str, actor: str, expected: int
    ) -> dict[str, Any]:
        record = self._load(scope, definition_id)
        self._expected(record, expected)
        draft = self._draft(record)
        try:
            verified = validate_bindings(
                scope, draft["content"].get("bindings", {}), self.binding_resolver
            )
        except BindingValidationFailure as exc:
            draft["validationErrors"] = [exc.reason]
            raise AgentDefinitionFailure(exc.reason, 409) from exc
        draft["state"] = "VALIDATED"
        draft["validatedAt"] = _now()
        draft["validationErrors"] = []
        draft["bindingValidation"] = {
            "status": "VALID",
            "verifiedReferences": verified,
            "executionAuthorityGranted": False,
        }
        record["lifecycleState"] = "VALIDATED"
        return self._replace(record, expected, "DRAFT_VALIDATED", actor, draft)

    def review(
        self,
        scope: DefinitionScope,
        definition_id: str,
        actor: str,
        expected: int,
        digest: str,
        decision: str,
        reason: str,
    ) -> dict[str, Any]:
        record = self._load(scope, definition_id)
        self._expected(record, expected)
        draft = self._draft(record)
        try:
            validate_bindings(
                scope, draft["content"].get("bindings", {}), self.binding_resolver
            )
        except BindingValidationFailure as exc:
            raise AgentDefinitionFailure(exc.reason, 409) from exc
        if draft["state"] != "VALIDATED":
            raise AgentDefinitionFailure("VALIDATION_REQUIRED", 409)
        if digest != draft["digest"]:
            raise AgentDefinitionFailure("EXACT_DIGEST_REQUIRED", 409)
        if decision != "APPROVE" or not reason.strip():
            raise AgentDefinitionFailure("HUMAN_REVIEW_REJECTED", 409)
        review = {
            "reviewId": _id("agent-review"),
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

    def publish(
        self,
        scope: DefinitionScope,
        definition_id: str,
        actor: str,
        expected: int,
        digest: str,
        review_id: str,
    ) -> dict[str, Any]:
        record = self._load(scope, definition_id)
        self._expected(record, expected)
        draft = self._draft(record)
        review = next(
            (r for r in record["reviews"] if r["reviewId"] == review_id), None
        )
        if (
            review is None
            or review["digest"] != digest
            or draft["digest"] != digest
            or draft["state"] != "HUMAN_REVIEWED"
        ):
            raise AgentDefinitionFailure("EXACT_REVIEW_REQUIRED", 409)
        draft["state"] = "PUBLISHED"
        draft["publishedAt"] = _now()
        record["publishedRevisionId"] = draft["revisionId"]
        record["currentDraftRevisionId"] = None
        record["lifecycleState"] = "PUBLISHED"
        return self._replace(record, expected, "REVISION_PUBLISHED", actor, draft)

    def successor(
        self, scope: DefinitionScope, definition_id: str, actor: str, expected: int
    ) -> dict[str, Any]:
        record = self._load(scope, definition_id)
        self._expected(record, expected)
        if record["currentDraftRevisionId"]:
            raise AgentDefinitionFailure("DRAFT_ALREADY_EXISTS", 409)
        published = self._published(record)
        revision = {
            "revisionId": _id("agent-revision"),
            "predecessorRevisionId": published["revisionId"],
            "state": "DRAFT",
            "content": copy.deepcopy(published["content"]),
            "createdAt": _now(),
        }
        revision["digest"] = _revision_digest(record, revision)
        record["revisions"].append(revision)
        record["currentDraftRevisionId"] = revision["revisionId"]
        record["lifecycleState"] = "DRAFT"
        return self._replace(record, expected, "SUCCESSOR_CREATED", actor, revision)

    def lifecycle(
        self,
        scope: DefinitionScope,
        definition_id: str,
        actor: str,
        expected: int,
        action: str,
        reason: str,
    ) -> dict[str, Any]:
        record = self._load(scope, definition_id)
        self._expected(record, expected)
        if not reason.strip():
            raise AgentDefinitionFailure("REASON_REQUIRED")
        if action in {"ENABLE", "DISABLE"}:
            record["enabled"] = action == "ENABLE"
        elif action == "DEPRECATE":
            self._published(record)
            record["lifecycleState"] = "DEPRECATED"
        elif action == "ARCHIVE":
            record["archived"] = True
            record["lifecycleState"] = "ARCHIVED"
        else:
            raise AgentDefinitionFailure("LIFECYCLE_ACTION_UNSUPPORTED")
        return self._replace(record, expected, action, actor, {"reason": reason})

    def impact(self, scope: DefinitionScope, definition_id: str) -> dict[str, Any]:
        record = self._load(scope, definition_id)
        published = record["publishedRevisionId"] is not None
        referenced = bool(record["relationships"])
        return {
            "definitionId": definition_id,
            "deletionPermitted": not published and not referenced,
            "publishedHistoryProtected": published,
            "consumerCount": len(record["relationships"]),
            "reasonCode": "DELETION_PERMITTED"
            if not published and not referenced
            else "PROTECTED_OR_REFERENCED",
        }

    def delete_draft(
        self, scope: DefinitionScope, definition_id: str, actor: str, expected: int
    ) -> None:
        record = self._load(scope, definition_id)
        self._expected(record, expected)
        impact = self.impact(scope, definition_id)
        if not impact["deletionPermitted"]:
            raise AgentDefinitionFailure("PROTECTED_OR_REFERENCED", 409)
        self.repository.delete_draft(
            scope,
            definition_id,
            expected_version=expected,
            tombstone={
                "definitionId": definition_id,
                "actor": actor,
                "deletedAt": _now(),
            },
        )

    def eligible(self, scope: DefinitionScope) -> list[dict[str, Any]]:
        eligible = []
        for record in self.repository.list(scope):
            if (
                record["publishedRevisionId"]
                and record["enabled"]
                and not record["archived"]
                and record["lifecycleState"] not in {"DEPRECATED", "ARCHIVED"}
            ):
                eligible.append(
                    {"definition": record, "revision": self._published(record)}
                )
        return eligible

    def rematch(
        self, scope: DefinitionScope, required_capabilities: list[str]
    ) -> dict[str, Any]:
        required = set(required_capabilities)
        candidates = [
            item
            for item in self.eligible(scope)
            if required.issubset(set(item["revision"]["content"]["capabilities"]))
        ]
        if not candidates:
            return {
                "outcome": "CAPABILITY_GAP",
                "requiredCapabilities": sorted(required),
            }
        selected = sorted(
            candidates,
            key=lambda item: (
                item["definition"]["definitionId"],
                item["revision"]["revisionId"],
            ),
        )[0]
        return {
            "outcome": "GOVERNED_MATCH",
            "definitionId": selected["definition"]["definitionId"],
            "revisionId": selected["revision"]["revisionId"],
            "digest": selected["revision"]["digest"],
            "executionAuthorityGranted": False,
        }

    def project(self, record: dict[str, Any]) -> dict[str, Any]:
        definition = copy.deepcopy(record)
        technical = {
            "definitionId": record["definitionId"],
            "namespace": record["namespace"],
            "securityDomain": record["securityDomain"],
            "aggregateVersion": record["aggregateVersion"],
            "publishedRevisionId": record["publishedRevisionId"],
            "revisionDigests": [
                {
                    "revisionId": r["revisionId"],
                    "digest": r["digest"],
                    "state": r["state"],
                }
                for r in record["revisions"]
            ],
            "limitations": record["limitations"],
            "governedBindings": copy.deepcopy(
                self._published(record)["content"].get("bindings", {})
                if record["publishedRevisionId"]
                else self._draft(record)["content"].get("bindings", {})
            ),
            "executionAuthorityGranted": False,
        }
        product = {
            "definitionId": record["definitionId"],
            "name": record["name"],
            "state": record["lifecycleState"],
            "enabled": record["enabled"],
            "revisionCount": len(record["revisions"]),
            "relationshipCount": len(record["relationships"]),
        }
        return {
            "definition": definition,
            "productProjection": product,
            "technicalProjection": technical,
        }

    @staticmethod
    def _fact(event: str, actor: str, subject: dict[str, Any]) -> dict[str, Any]:
        return {
            "factId": _id("agent-fact"),
            "event": event,
            "actor": actor,
            "recordedAt": _now(),
            "subject": copy.deepcopy(subject),
        }

    def _replace(
        self,
        record: dict[str, Any],
        expected: int,
        event: str,
        actor: str,
        subject: dict[str, Any],
    ) -> dict[str, Any]:
        record["aggregateVersion"] = expected + 1
        record["updatedAt"] = _now()
        try:
            stored = self.repository.replace(
                record,
                expected_version=expected,
                fact=self._fact(event, actor, subject),
            )
        except AgentDefinitionConflict as exc:
            raise AgentDefinitionFailure("STALE_AGENT_DEFINITION", 409) from exc
        return self.project(stored)

    def _load(self, scope: DefinitionScope, definition_id: str) -> dict[str, Any]:
        try:
            return self.repository.get(scope, definition_id)
        except AgentDefinitionNotFound as exc:
            raise AgentDefinitionFailure("AGENT_DEFINITION_NOT_FOUND", 404) from exc

    @staticmethod
    def _expected(record: dict[str, Any], expected: int) -> None:
        if record["aggregateVersion"] != expected:
            raise AgentDefinitionFailure("STALE_AGENT_DEFINITION", 409)

    @staticmethod
    def _draft(record: dict[str, Any]) -> dict[str, Any]:
        revision_id = record["currentDraftRevisionId"]
        if revision_id is None:
            raise AgentDefinitionFailure("DRAFT_REQUIRED", 409)
        return next(r for r in record["revisions"] if r["revisionId"] == revision_id)

    @staticmethod
    def _published(record: dict[str, Any]) -> dict[str, Any]:
        revision_id = record["publishedRevisionId"]
        if revision_id is None:
            raise AgentDefinitionFailure("PUBLISHED_REVISION_REQUIRED", 409)
        return next(r for r in record["revisions"] if r["revisionId"] == revision_id)
