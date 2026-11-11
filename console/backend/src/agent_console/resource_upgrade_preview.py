"""Exact, read-only selected upgrade preview on the caller's authorized connection.

Publication callers request row locks before rebuilding this preview. Immutable
source references and generated successors, rather than a client-authored object
body, define the reviewed change. This module does not grant or publish anything.
"""

import json
from dataclasses import asdict, dataclass

from .business_capability import FixedReference
from .business_capability_publication import change_preview
from .business_capability_publication_postgres import CapabilityPublicationRepository
from .digital_employee_definition import EmployeeRevision, digest, identifier
from .execution_domain import ScopeIdentity
from .resource_management import target
from .resource_upgrade_batch_postgres import UpgradeBatchError
from .resource_upgrade_owners import CapabilityPublication, EmployeePublication
from .resource_upgrade_selection import (
    SelectedReplacement,
    capability_successor,
    employee_successor,
)
from .skill_resource_testing import coverage
from .workbench_business_problem import OwnerPrincipal
from .workbench_prepared_resources import bind_service, reference


@dataclass(frozen=True)
class ConsumerSelection:
    original: FixedReference
    successor_revision_id: str

    def __post_init__(self):
        identifier(self.successor_revision_id)
        if self.successor_revision_id == self.original.revision_id:
            raise UpgradeBatchError("UPGRADE_NEW_REVISION_REQUIRED")


@dataclass(frozen=True)
class UpgradeSelection:
    old_skill: FixedReference
    new_skill: FixedReference
    employees: tuple[ConsumerSelection, ...]
    capabilities: tuple[ConsumerSelection, ...]
    resource_kind: str = "skill"

    def record(self):
        value = asdict(self)
        if self.resource_kind == "skill":
            value.pop("resource_kind")
        return value

    def __post_init__(self):
        if self.resource_kind not in {"skill", "mcp"}:
            raise UpgradeBatchError("UPGRADE_RESOURCE_KIND_INVALID")
        if self.old_skill.resource_id != self.new_skill.resource_id:
            raise UpgradeBatchError("UPGRADE_RESOURCE_IDENTITY_CHANGED")
        if self.old_skill.revision_id == self.new_skill.revision_id:
            raise UpgradeBatchError("UPGRADE_NEW_REVISION_REQUIRED")
        if len(self.employees) + len(self.capabilities) > 64:
            raise UpgradeBatchError("UPGRADE_SELECTION_LIMIT")
        for values in (self.employees, self.capabilities):
            if len({v.original.resource_id for v in values}) != len(values):
                raise UpgradeBatchError("UPGRADE_DUPLICATE_SELECTION")


@dataclass(frozen=True)
class PreparedUpgrade:
    preview: dict
    skill_version: int
    employees: tuple[EmployeePublication, ...]
    capabilities: tuple[CapabilityPublication, ...]

    @property
    def review_digest(self):
        return digest(self.preview)


class SelectedUpgradePreview:
    def __init__(self, skill_service, employees, capabilities, capability_references):
        self.skill_service = skill_service
        self.employees = employees
        self.capabilities = capabilities
        self.capability_references = capability_references

    @staticmethod
    def _require(call, owner, action, exact):
        return call.authority.require(
            OwnerPrincipal(
                call.context.principal_id,
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
            ),
            owner,
            action,
            exact,
        )

    def authorize_sources(self, call, selected):
        """Also used before receipt replay; never skip fresh source authorization."""
        skill = selected.new_skill
        self._require(
            call,
            "SKILL",
            "MANAGE_RESOURCE",
            target(selected.resource_kind, skill.resource_id),
        )
        for ref in (selected.old_skill, skill):
            self._require(
                call,
                "SKILL",
                "READ_RESOURCE",
                reference(selected.resource_kind, ref.resource_id, ref.revision_id),
            )
        if selected.employees:
            self._require(call, "EMPLOYEE", "CREATE", "employee:collection")
        for item in selected.employees:
            ref = item.original
            self._require(
                call,
                "EMPLOYEE",
                "READ",
                f"employee:{ref.resource_id}:{ref.revision_id}",
            )
            for action in ("VALIDATE", "APPROVE", "PUBLISH"):
                self._require(
                    call, "EMPLOYEE", action, f"employee:{ref.resource_id}:aggregate"
                )
        for item in selected.capabilities:
            ref = item.original
            self._require(
                call,
                "BUSINESS_CAPABILITY",
                "READ",
                f"business-capability:{ref.resource_id}:{ref.revision_id}",
            )
            self._require(
                call,
                "BUSINESS_CAPABILITY",
                "REVISE",
                f"business-capability:{ref.resource_id}:aggregate",
            )

    @staticmethod
    def _lock(call, selected):
        # Existing owners take aggregate advisory locks before their row locks.
        # Reserve those same locks without waiting before taking any rows: a writer
        # holding an advisory lock must never wait for a row held by this batch.
        scope = (call.context.scope.tenant_id, call.context.scope.security_domain)
        for seed, values in ((0, selected.employees), (54, selected.capabilities)):
            for item in sorted(values, key=lambda v: v.original.resource_id):
                key = (*scope, item.original.resource_id)
                encoded = json.dumps(key) if seed == 0 else digest(key)
                acquired = call.connection.execute(
                    "SELECT pg_try_advisory_xact_lock("
                    "hashtextextended(%s, %s)) acquired",
                    (encoded, seed),
                ).fetchone()["acquired"]
                if not acquired:
                    raise UpgradeBatchError("UPGRADE_CONCURRENT_CHANGE")
        call.connection.execute(
            "SELECT resource_id FROM skill_mcp_resource.resources WHERE namespace=%s "
            "AND security_domain=%s AND kind=%s "
            "AND resource_id=%s FOR UPDATE NOWAIT",
            (*scope, selected.resource_kind, selected.new_skill.resource_id),
        )
        for table, column, values in (
            (
                "digital_employee_definition.definitions",
                "definition_id",
                selected.employees,
            ),
            ("business_capability.definitions", "capability_id", selected.capabilities),
        ):
            for item in sorted(values, key=lambda v: v.original.resource_id):
                call.connection.execute(
                    f"SELECT {column} FROM {table} WHERE namespace=%s "
                    f"AND security_domain=%s AND {column}=%s FOR UPDATE NOWAIT",
                    (*scope, item.original.resource_id),
                )

    def build(self, call, selected: UpgradeSelection, *, lock=False):
        self.authorize_sources(call, selected)
        if lock:
            self._lock(call, selected)
        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        service = bind_service(self.skill_service, call.connection)
        record = service.repository.get(
            service.scope(scope.namespace, scope.security_domain),
            selected.resource_kind,
            selected.new_skill.resource_id,
        )
        if (
            record["publishedRevisionId"] != selected.old_skill.revision_id
            or record["currentDraftRevisionId"] != selected.new_skill.revision_id
        ):
            raise UpgradeBatchError("UPGRADE_SKILL_HEAD_CHANGED")
        revisions = {r["revisionId"]: r for r in record["revisions"]}
        for ref in (selected.old_skill, selected.new_skill):
            if (
                ref.revision_id not in revisions
                or revisions[ref.revision_id]["digest"] != ref.digest
            ):
                raise UpgradeBatchError("UPGRADE_SKILL_REFERENCE_CHANGED")
        if (
            selected.resource_kind == "skill"
            and not coverage(record, revisions[selected.new_skill.revision_id])["ready"]
        ):
            raise UpgradeBatchError("CURRENT_OPERATION_TESTS_REQUIRED")
        changes = [
            SelectedReplacement(
                scope,
                selected.resource_kind.upper(),
                selected.old_skill,
                selected.new_skill,
            )
        ]
        employee_results, capability_results = [], []
        employee_views, capability_views = [], []
        for item in sorted(selected.employees, key=lambda v: v.original.resource_id):
            ref = item.original
            value = self.employees.read_revision_for_workbench(
                call.connection,
                scope,
                ref.resource_id,
                ref.revision_id,
                authorized=True,
            )
            heads = self.employees.authoring_heads_for_workbench(
                call.connection, scope, ref.resource_id, authorized=True
            )
            if (
                heads["head"] != ref.revision_id
                or heads["publication"] != ref.revision_id
            ):
                raise UpgradeBatchError("UPGRADE_EMPLOYEE_HEAD_OR_DRAFT_CONFLICT")
            if (
                value["digest"] != ref.digest
                or value["publicationState"] != "PUBLISHED"
            ):
                raise UpgradeBatchError("UPGRADE_EMPLOYEE_REFERENCE_CHANGED")
            old = EmployeeRevision.from_record(value["revision"])
            new = employee_successor(old, item.successor_revision_id, changes[:1])
            employee_results.append(EmployeePublication(new, heads["aggregateVersion"]))
            changes.append(
                SelectedReplacement(
                    scope,
                    "EMPLOYEE",
                    ref,
                    FixedReference(new.definition_id, new.revision_id, new.digest),
                )
            )
            employee_views.append(
                {
                    "before": old.record,
                    "after": new.record,
                    "aggregateVersion": heads["aggregateVersion"],
                }
            )
        for item in sorted(selected.capabilities, key=lambda v: v.original.resource_id):
            ref = item.original
            old = self.capabilities.read(
                call.connection, scope, ref.resource_id, ref.revision_id
            )
            self.capability_references.validate(call, old, require_published=True)
            head = call.connection.execute(
                "SELECT head_revision_id,aggregate_version "
                "FROM business_capability.definitions "
                "WHERE namespace=%s AND security_domain=%s AND capability_id=%s",
                (scope.namespace, scope.security_domain, ref.resource_id),
            ).fetchone()
            publication = CapabilityPublicationRepository.latest(
                call.connection, scope, ref.resource_id
            )
            if (
                not head
                or head["head_revision_id"] != ref.revision_id
                or not publication
                or publication["revision_id"] != ref.revision_id
            ):
                raise UpgradeBatchError("UPGRADE_CAPABILITY_HEAD_OR_DRAFT_CONFLICT")
            if (
                old.content_digest != ref.digest
                or publication["revision_digest"] != ref.digest
            ):
                raise UpgradeBatchError("UPGRADE_CAPABILITY_REFERENCE_CHANGED")
            new = capability_successor(old, item.successor_revision_id, changes)
            # Saving the new revision advances the aggregate once before publication.
            view = change_preview(
                new,
                old,
                aggregate_version=head["aggregate_version"] + 1,
                generation=call.policy_generation,
            )
            capability_results.append(
                CapabilityPublication(
                    new, head["aggregate_version"], view["impactDigest"]
                )
            )
            capability_views.append(view)
        preview = {
            "schemaVersion": "selected-resource-upgrade-preview.v1",
            "scope": asdict(scope),
            "actorId": call.context.principal_id,
            "authorityGeneration": call.policy_generation,
            "recoveryEpoch": call.recovery_epoch,
            "selection": selected.record(),
            "skill": {
                "name": record["name"],
                "before": asdict(selected.old_skill),
                "after": asdict(selected.new_skill),
                "aggregateVersion": record["aggregateVersion"],
            },
            "employees": employee_views,
            "capabilities": capability_views,
            "unselectedReferencesChanged": False,
            "historicalReferencesChanged": False,
            "executionStarted": False,
        }
        return PreparedUpgrade(
            preview,
            record["aggregateVersion"],
            tuple(employee_results),
            tuple(capability_results),
        )
