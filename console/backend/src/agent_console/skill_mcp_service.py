"""Lifecycle, binding and bounded invocation authority for Skill/MCP resources."""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from agent_console.definition_authority import canonical_digest
from agent_console.skill_mcp_repository import (
    ResourceScope,
    SkillMcpConflict,
    SkillMcpNotFound,
    SkillMcpRepository,
)


class SkillMcpFailure(RuntimeError):
    def __init__(self, reason: str, status: int = 422) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4()}"


class SkillMcpService:
    KINDS: ClassVar[set[str]] = {"skill", "mcp"}

    def __init__(self, repository: SkillMcpRepository) -> None:
        self.repository = repository
        repository.compatibility()

    @staticmethod
    def scope(namespace: str, security_domain: str) -> ResourceScope:
        if not namespace or not security_domain:
            raise SkillMcpFailure("TRUSTED_SCOPE_REQUIRED", 403)
        return ResourceScope(namespace, security_domain)

    def create(
        self,
        scope: ResourceScope,
        kind: str,
        actor: str,
        name: str,
        content: dict[str, Any],
    ) -> dict[str, Any]:
        self._kind(kind)
        self._content(kind, content)
        now, resource_id, revision_id = (
            _now(),
            _id(f"{kind}-definition"),
            _id(f"{kind}-revision"),
        )
        record: dict[str, Any] = {
            "resourceId": resource_id,
            "kind": kind,
            "name": name.strip(),
            "namespace": scope.namespace,
            "securityDomain": scope.security_domain,
            "aggregateVersion": 1,
            "lifecycleState": "DRAFT",
            "enabled": True,
            "archived": False,
            "currentDraftRevisionId": revision_id,
            "publishedRevisionId": None,
            "revisions": [],
            "reviews": [],
            "facts": [],
            "relationships": [],
            "bindings": [],
            "invocations": [],
            "createdAt": now,
            "updatedAt": now,
            "limitations": [
                "PRIVATE_WORKBENCH_API",
                "NO_EXTERNAL_MCP_DELETION_CLAIM",
                "BOUNDED_TEST_INVOCATION_ONLY",
            ],
        }
        revision = {
            "revisionId": revision_id,
            "predecessorRevisionId": None,
            "state": "DRAFT",
            "content": copy.deepcopy(content),
            "createdAt": now,
        }
        revision["digest"] = self._digest(record, revision)
        record["revisions"].append(revision)
        record["facts"].append(self._fact("DRAFT_CREATED", actor, revision))
        try:
            return self.repository.create(record)
        except SkillMcpConflict as exc:
            raise SkillMcpFailure(str(exc), 409) from exc

    def list(self, scope: ResourceScope, kind: str) -> list[dict[str, Any]]:
        self._kind(kind)
        return self.repository.list(scope, kind)

    def get(self, scope: ResourceScope, kind: str, resource_id: str) -> dict[str, Any]:
        try:
            return self.project(self.repository.get(scope, kind, resource_id))
        except SkillMcpNotFound as exc:
            raise SkillMcpFailure("RESOURCE_NOT_FOUND", 404) from exc

    def edit(
        self,
        scope: ResourceScope,
        kind: str,
        resource_id: str,
        actor: str,
        expected: int,
        content: dict[str, Any],
    ) -> dict[str, Any]:
        self._content(kind, content)
        record = self._load(scope, kind, resource_id)
        self._expected(record, expected)
        predecessor = self._draft(record)
        revision = {
            "revisionId": _id(f"{kind}-revision"),
            "predecessorRevisionId": predecessor["revisionId"],
            "state": "DRAFT",
            "content": copy.deepcopy(content),
            "createdAt": _now(),
        }
        revision["digest"] = self._digest(record, revision)
        record["revisions"].append(revision)
        record["currentDraftRevisionId"] = revision["revisionId"]
        record["lifecycleState"] = "DRAFT"
        return self._replace(record, expected, "DRAFT_EDITED", actor, revision)

    def validate(
        self,
        scope: ResourceScope,
        kind: str,
        resource_id: str,
        actor: str,
        expected: int,
    ) -> dict[str, Any]:
        record = self._load(scope, kind, resource_id)
        self._expected(record, expected)
        draft = self._draft(record)
        self._content(kind, draft["content"])
        draft.update(
            {"state": "VALIDATED", "validatedAt": _now(), "validationErrors": []}
        )
        record["lifecycleState"] = "VALIDATED"
        return self._replace(record, expected, "DRAFT_VALIDATED", actor, draft)

    def review(
        self,
        scope: ResourceScope,
        kind: str,
        resource_id: str,
        actor: str,
        expected: int,
        digest: str,
        decision: str,
        reason: str,
    ) -> dict[str, Any]:
        record = self._load(scope, kind, resource_id)
        self._expected(record, expected)
        draft = self._draft(record)
        if draft["state"] != "VALIDATED":
            raise SkillMcpFailure("VALIDATION_REQUIRED", 409)
        if digest != draft["digest"]:
            raise SkillMcpFailure("EXACT_DIGEST_REQUIRED", 409)
        if decision != "APPROVE" or not reason.strip():
            raise SkillMcpFailure("HUMAN_REVIEW_REJECTED", 409)
        review = {
            "reviewId": _id(f"{kind}-review"),
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
        scope: ResourceScope,
        kind: str,
        resource_id: str,
        actor: str,
        expected: int,
        digest: str,
        review_id: str,
    ) -> dict[str, Any]:
        record = self._load(scope, kind, resource_id)
        self._expected(record, expected)
        draft = self._draft(record)
        review = next(
            (r for r in record["reviews"] if r["reviewId"] == review_id), None
        )
        if (
            not review
            or review["digest"] != digest
            or draft["digest"] != digest
            or draft["state"] != "HUMAN_REVIEWED"
        ):
            raise SkillMcpFailure("EXACT_REVIEW_REQUIRED", 409)
        draft.update({"state": "PUBLISHED", "publishedAt": _now()})
        record.update(
            {
                "publishedRevisionId": draft["revisionId"],
                "currentDraftRevisionId": None,
                "lifecycleState": "PUBLISHED",
            }
        )
        return self._replace(record, expected, "REVISION_PUBLISHED", actor, draft)

    def successor(
        self,
        scope: ResourceScope,
        kind: str,
        resource_id: str,
        actor: str,
        expected: int,
    ) -> dict[str, Any]:
        record = self._load(scope, kind, resource_id)
        self._expected(record, expected)
        if record["currentDraftRevisionId"]:
            raise SkillMcpFailure("DRAFT_ALREADY_EXISTS", 409)
        published = self._published(record)
        revision = {
            "revisionId": _id(f"{kind}-revision"),
            "predecessorRevisionId": published["revisionId"],
            "state": "DRAFT",
            "content": copy.deepcopy(published["content"]),
            "createdAt": _now(),
        }
        revision["digest"] = self._digest(record, revision)
        record["revisions"].append(revision)
        record["currentDraftRevisionId"] = revision["revisionId"]
        record["lifecycleState"] = "DRAFT"
        return self._replace(record, expected, "SUCCESSOR_CREATED", actor, revision)

    def lifecycle(
        self,
        scope: ResourceScope,
        kind: str,
        resource_id: str,
        actor: str,
        expected: int,
        action: str,
        reason: str,
    ) -> dict[str, Any]:
        record = self._load(scope, kind, resource_id)
        self._expected(record, expected)
        if not reason.strip():
            raise SkillMcpFailure("REASON_REQUIRED")
        if action in {"ENABLE", "DISABLE"}:
            record["enabled"] = action == "ENABLE"
        elif action == "DEPRECATE":
            self._published(record)
            record["lifecycleState"] = "DEPRECATED"
        elif action == "ARCHIVE":
            record["archived"] = True
            record["lifecycleState"] = "ARCHIVED"
        else:
            raise SkillMcpFailure("LIFECYCLE_ACTION_UNSUPPORTED")
        return self._replace(record, expected, action, actor, {"reason": reason})

    def bind(
        self,
        scope: ResourceScope,
        skill_id: str,
        actor: str,
        expected: int,
        skill_revision_id: str,
        mcp_id: str,
        mcp_revision_id: str,
        capability: str,
        reason: str,
    ) -> dict[str, Any]:
        skill = self._load(scope, "skill", skill_id)
        mcp = self._load(scope, "mcp", mcp_id)
        self._expected(skill, expected)
        sr, mr = self._published(skill), self._published(mcp)
        if sr["revisionId"] != skill_revision_id or mr["revisionId"] != mcp_revision_id:
            raise SkillMcpFailure("EXACT_PUBLISHED_REVISIONS_REQUIRED", 409)
        if (
            not skill["enabled"]
            or not mcp["enabled"]
            or capability not in sr["content"]["capabilities"]
            or capability not in mr["content"]["capabilities"]
        ):
            raise SkillMcpFailure("CAPABILITY_BINDING_NOT_ELIGIBLE", 409)
        binding = {
            "bindingId": _id("skill-mcp-binding"),
            "skillRevisionId": skill_revision_id,
            "mcpResourceId": mcp_id,
            "mcpRevisionId": mcp_revision_id,
            "capability": capability,
            "reason": reason,
            "createdAt": _now(),
        }
        skill["bindings"].append(binding)
        skill["relationships"].append({"type": "USES_MCP_CAPABILITY", **binding})
        return self._replace(skill, expected, "CAPABILITY_BOUND", actor, binding)

    def invoke(
        self,
        scope: ResourceScope,
        skill_id: str,
        actor: str,
        expected: int,
        binding_id: str,
        authorization: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        skill = self._load(scope, "skill", skill_id)
        self._expected(skill, expected)
        binding = next(
            (b for b in skill["bindings"] if b["bindingId"] == binding_id), None
        )
        if not binding:
            raise SkillMcpFailure("BINDING_NOT_FOUND", 404)
        if authorization != "ALLOW_BOUNDED_CAPABILITY_TEST":
            raise SkillMcpFailure("INVOCATION_NOT_AUTHORIZED", 403)
        mcp = self._load(scope, "mcp", binding["mcpResourceId"])
        published = self._published(mcp)
        if published["revisionId"] != binding["mcpRevisionId"] or not mcp["enabled"]:
            raise SkillMcpFailure("BOUND_REVISION_UNAVAILABLE", 409)
        invocation = {
            "invocationId": _id("capability-test"),
            "bindingId": binding_id,
            "actor": actor,
            "status": "SUCCEEDED",
            "result": {
                "capability": binding["capability"],
                "echo": copy.deepcopy(inputs),
            },
            "evidence": {"redacted": True, "credentialMaterial": "NOT_RECORDED"},
            "invokedAt": _now(),
        }
        skill["invocations"].append(invocation)
        projected = self._replace(
            skill,
            expected,
            "BOUNDED_CAPABILITY_TESTED",
            actor,
            {
                "invocationId": invocation["invocationId"],
                "status": "SUCCEEDED",
                "redacted": True,
            },
        )
        projected["invocation"] = invocation
        return projected

    def impact(
        self, scope: ResourceScope, kind: str, resource_id: str
    ) -> dict[str, Any]:
        record = self._load(scope, kind, resource_id)
        protected = bool(
            record["publishedRevisionId"]
            or record["relationships"]
            or record["bindings"]
            or record["invocations"]
        )
        return {
            "resourceId": resource_id,
            "deletionPermitted": not protected,
            "publishedHistoryProtected": bool(record["publishedRevisionId"]),
            "consumerCount": len(record["relationships"]),
            "reasonCode": "DELETION_PERMITTED"
            if not protected
            else "PROTECTED_OR_REFERENCED",
            "externalMcpDeletionClaim": False,
        }

    def delete_draft(
        self,
        scope: ResourceScope,
        kind: str,
        resource_id: str,
        actor: str,
        expected: int,
    ) -> None:
        if not self.impact(scope, kind, resource_id)["deletionPermitted"]:
            raise SkillMcpFailure("PROTECTED_OR_REFERENCED", 409)
        self.repository.delete_draft(
            scope,
            kind,
            resource_id,
            expected_version=expected,
            tombstone={
                "resourceId": resource_id,
                "kind": kind,
                "actor": actor,
                "deletedAt": _now(),
                "contentRetained": False,
            },
        )

    def project(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "resource": copy.deepcopy(record),
            "productProjection": {
                "resourceId": record["resourceId"],
                "kind": record["kind"],
                "name": record["name"],
                "state": record["lifecycleState"],
                "enabled": record["enabled"],
                "revisionCount": len(record["revisions"]),
                "consumerCount": len(record["relationships"]),
            },
            "technicalProjection": {
                "resourceId": record["resourceId"],
                "kind": record["kind"],
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
                "bindings": copy.deepcopy(record["bindings"]),
                "limitations": record["limitations"],
            },
        }

    @staticmethod
    def _kind(kind: str) -> None:
        if kind not in SkillMcpService.KINDS:
            raise SkillMcpFailure("RESOURCE_KIND_UNSUPPORTED", 404)

    @staticmethod
    def _content(kind: str, value: dict[str, Any]) -> None:
        if not str(value.get("description", "")).strip() or not value.get(
            "capabilities"
        ):
            raise SkillMcpFailure("INVALID_RESOURCE_CONTENT")
        if kind == "skill" and not str(value.get("instructions", "")).strip():
            raise SkillMcpFailure("SKILL_INSTRUCTIONS_REQUIRED")
        if kind == "mcp" and not str(value.get("endpoint", "")).startswith(
            ("http://", "https://")
        ):
            raise SkillMcpFailure("MCP_ENDPOINT_REQUIRED")

    def _load(
        self, scope: ResourceScope, kind: str, resource_id: str
    ) -> dict[str, Any]:
        self._kind(kind)
        try:
            return self.repository.get(scope, kind, resource_id)
        except SkillMcpNotFound as exc:
            raise SkillMcpFailure("RESOURCE_NOT_FOUND", 404) from exc

    @staticmethod
    def _expected(record: dict[str, Any], expected: int) -> None:
        if record["aggregateVersion"] != expected:
            raise SkillMcpFailure("STALE_RESOURCE", 409)

    @staticmethod
    def _draft(record: dict[str, Any]) -> dict[str, Any]:
        revision = next(
            (
                r
                for r in record["revisions"]
                if r["revisionId"] == record["currentDraftRevisionId"]
            ),
            None,
        )
        if not revision:
            raise SkillMcpFailure("DRAFT_REQUIRED", 409)
        return revision

    @staticmethod
    def _published(record: dict[str, Any]) -> dict[str, Any]:
        revision = next(
            (
                r
                for r in record["revisions"]
                if r["revisionId"] == record["publishedRevisionId"]
            ),
            None,
        )
        if not revision:
            raise SkillMcpFailure("PUBLISHED_REVISION_REQUIRED", 409)
        return revision

    @staticmethod
    def _digest(record: dict[str, Any], revision: dict[str, Any]) -> str:
        return canonical_digest(
            {
                "resourceId": record["resourceId"],
                "kind": record["kind"],
                "revisionId": revision["revisionId"],
                "predecessorRevisionId": revision.get("predecessorRevisionId"),
                "namespace": record["namespace"],
                "securityDomain": record["securityDomain"],
                "content": revision["content"],
                "schemaVersion": "skill-mcp-resource-revision.v1",
            },
            domain="skill-mcp-resource-lifecycle-v1",
        )

    @staticmethod
    def _fact(event: str, actor: str, subject: dict[str, Any]) -> dict[str, Any]:
        return {
            "factId": _id("skill-mcp-fact"),
            "event": event,
            "actor": actor,
            "subject": copy.deepcopy(subject),
            "recordedAt": _now(),
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
        fact = self._fact(event, actor, subject)
        try:
            return self.project(
                self.repository.replace(record, expected_version=expected, fact=fact)
            )
        except SkillMcpConflict as exc:
            raise SkillMcpFailure(str(exc), 409) from exc
