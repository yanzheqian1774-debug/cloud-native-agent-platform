# ruff: noqa: E501 -- Existing owner SQL with explicit scope and immutable receipts.
"""Bounded ontology maintenance facade; all writes remain in the ontology owner."""

import json
from datetime import timedelta
from types import SimpleNamespace

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError, ExactGrant
from .ontology_domain import OntologyCommand, OntologyError
from .ontology_maintenance_binding import (
    REQUEST_PREFIX,
    REVISION_PREFIX,
    SCHEMA,
    command_key,
)
from .ontology_management_policy import MaintenanceCommand
from .ontology_service import OntologyService, resource
from .resource_automation import ResourceAutomation, bound_grants
from .resource_use_domain import canonical_digest
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError


class CommandTargets:
    """One trusted call, one new revision, two exact grants; never global targets."""

    def __init__(self, delegate, context, connection, members):
        self.delegate, self.context, self.connection = delegate, context, connection
        self.members = members

    def is_known_exact_target(self, context, grant, *, connection=None):
        if (
            context == self.context
            and connection is self.connection
            and grant in self.members
        ):
            return True
        return self.delegate is not None and self.delegate.is_known_exact_target(
            context, grant, connection=connection
        )


class OntologyManagement:
    def __init__(self, policy, grants):
        self.policy, self.grants = policy, grants

    def creator(self, call, identity):
        rows = call.connection.execute(
            "SELECT p.result AS admission,p.actor_id AS creator_actor,f.command_digest FROM execution_authority.prepared_resource_commands p JOIN business_ontology.lifecycle_facts f ON f.namespace=p.namespace AND f.security_domain=p.security_domain AND f.actor=p.actor_id AND f.request_key=p.result->'ownerCommand'->>'request_key' AND f.ontology_id=p.result->>'ontologyId' AND f.revision_id=p.result->'ownerCommand'->>'revision_id' AND f.action='CREATE' WHERE p.namespace=%s AND p.security_domain=%s AND p.result->>'schemaVersion'=%s AND p.result->>'action'='CREATE' AND p.result->>'ontologyId'=%s LIMIT 2",
            (
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
                SCHEMA,
                identity,
            ),
        ).fetchall()
        if len(rows) != 1:
            return None
        record = rows[0]["admission"]
        expected = canonical_digest(
            {
                "identity": identity,
                "action": "CREATE",
                "command": record["ownerCommand"],
            }
        )
        if (
            record.get("actor") != rows[0]["creator_actor"]
            or rows[0]["command_digest"] != expected
            or record.get("scope")
            != [
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
            ]
        ):
            return None
        return record.get("actor")

    def scope(self, call, identity, action):
        issuer = self.policy.authenticate(self.grants, call.context)
        work = self.policy.work(
            call.context,
            identity,
            action,
            self.grants.clock(),
            created_by=self.creator(call, identity),
        )
        if self.grants.generation.generation != call.policy_generation:
            raise AuthorityError("ONTOLOGY_MANAGEMENT_GENERATION_CHANGED")
        return issuer, work

    def capabilities(self, call, identity):
        from typing import get_args

        from .ontology_management_policy import Action

        allowed = []
        creation_available = False
        try:
            self.policy.authenticate(self.grants, call.context)
            if self.grants.generation.generation != call.policy_generation:
                raise AuthorityError("ONTOLOGY_MANAGEMENT_GENERATION_CHANGED")
            now = self.grants.clock()
            creator = self.creator(call, identity)
            creation_available = any(
                s.namespace == call.context.scope.tenant_id
                and s.securityDomain == call.context.scope.security_domain
                and s.subject == call.context.principal_id
                and "CREATE" in s.actions
                and s.expiresAt.tzinfo is not None
                and s.expiresAt > now
                and (s.ontologyIds or s.createPrefix)
                for s in self.policy.workScopes
            )
            for action in get_args(Action):
                try:
                    self.policy.work(
                        call.context,
                        identity,
                        action,
                        self.grants.clock(),
                        created_by=creator,
                    )
                    allowed.append(action)
                except AuthorityError:
                    continue
        except (AuthorityError, OSError, ValueError):
            pass
        return {
            "schemaVersion": "ontology-maintenance-capabilities.v1",
            "ontologyId": identity,
            "allowedActions": allowed,
            "writeEligible": bool(allowed),
            "creationAvailable": creation_available,
        }

    def read_required(self, call, identity, revision):
        p = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        call.authority.require(
            p, "BUSINESS_ONTOLOGY", "READ", resource(identity, revision)
        )

    def _row(self, call, key):
        return call.connection.execute(
            "SELECT digest,result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
                call.context.principal_id,
                command_key(key),
            ),
        ).fetchone()

    def _outcome(self, call, record):
        row = call.connection.execute(
            "SELECT result FROM business_ontology.lifecycle_facts WHERE namespace=%s AND security_domain=%s AND actor=%s AND request_key=%s AND ontology_id=%s",
            (
                *record["scope"],
                call.context.principal_id,
                record["ownerCommand"]["request_key"],
                record["ontologyId"],
            ),
        ).fetchone()
        if not row:
            raise WorkbenchOwnerError("ONTOLOGY_COMMAND_NOT_FOUND", 404)
        return row["result"]

    def receipt(self, call, key):
        row = self._row(call, key)
        record = row["result"] if row else None
        from .ontology_maintenance_read import SCHEMA as READ_SCHEMA
        from .ontology_maintenance_read import receipt

        if record and record.get("schemaVersion") == READ_SCHEMA:
            if record.get("command", {}).get("commandKey") != key:
                raise WorkbenchOwnerError("ONTOLOGY_COMMAND_NOT_FOUND", 404)
            return receipt(self, call, record)
        if (
            not record
            or record.get("schemaVersion") != SCHEMA
            or record.get("actor") != call.context.principal_id
            or record.get("scope")
            != [call.context.scope.tenant_id, call.context.scope.security_domain]
            or record.get("command", {}).get("commandKey") != key
        ):
            raise WorkbenchOwnerError("ONTOLOGY_COMMAND_NOT_FOUND", 404)
        self.read_required(
            call, record["ontologyId"], record["ownerCommand"]["revision_id"]
        )
        eligible = False
        try:
            self.scope(call, record["ontologyId"], record["action"])
            p = OwnerPrincipal(call.context.principal_id, *record["scope"])
            call.authority.require(
                p,
                "BUSINESS_ONTOLOGY",
                record["action"],
                resource(record["ontologyId"], record["ownerCommand"]["revision_id"]),
            )
            from datetime import datetime

            eligible = (
                record["generation"] == call.policy_generation
                and datetime.fromisoformat(record["expiresAt"]) > self.grants.clock()
            )
        except (AuthorityError, OSError, ValueError):
            pass
        return {
            "schemaVersion": "ontology-maintenance-receipt.v1",
            "commandKey": key,
            "ontologyId": record["ontologyId"],
            "action": record["action"],
            "outcome": self._outcome(call, record),
            "writeEligible": eligible,
            "policyDecisionId": record["policyDecisionId"],
            "modelCalls": 0,
            "executionStarted": False,
        }

    def handle(self, call):
        if call.payload.get("action") == "PREPARE_READ":
            from .ontology_maintenance_read import prepare

            return prepare(self, call)
        cmd = MaintenanceCommand.model_validate(call.payload)
        issuer, work = self.scope(call, cmd.ontologyId, cmd.action)
        scope = (call.context.scope.tenant_id, call.context.scope.security_domain)
        actor, c = call.context.principal_id, call.connection
        key, digest = (
            command_key(cmd.commandKey),
            canonical_digest(cmd.model_dump(mode="json")),
        )
        for lock in sorted(
            (
                [*scope, actor, REQUEST_PREFIX + canonical_digest(cmd.commandKey)],
                [*scope, cmd.ontologyId],
            )
        ):
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (json.dumps(lock),),
            )
        prior = self._row(call, cmd.commandKey)
        if prior:
            if (
                prior["digest"] != digest
                or prior["result"].get("schemaVersion") != SCHEMA
            ):
                raise OntologyError("ONTOLOGY_MANAGEMENT_COMMAND_CONFLICT")
            record = prior["result"]
            # Owner verifies current grants, generation, expiry and exact command
            # before lifecycle replay. Never silently renew an expired command.
            OntologyService(call).handle(
                cmd.action, cmd.ontologyId, record["ownerCommand"]
            )
            return self.receipt(call, cmd.commandKey)
        service = OntologyService(call)
        head = c.execute(
            "SELECT * FROM business_ontology.definitions WHERE namespace=%s AND security_domain=%s AND ontology_id=%s FOR UPDATE",
            (*scope, cmd.ontologyId),
        ).fetchone()
        if (head["version"] if head else 0) != cmd.expectedVersion:
            raise OntologyError("ONTOLOGY_VERSION_CONFLICT")
        if cmd.action == "CREATE":
            if (
                head
                or cmd.baseRevision
                or cmd.baseDigest
                or cmd.revision
                or cmd.digest
                or cmd.content is None
            ):
                raise OntologyError("ONTOLOGY_MAINTENANCE_CREATE_INVALID")
        elif cmd.action == "REVISE":
            if (
                not head
                or cmd.baseRevision != head["head_revision"]
                or not cmd.baseDigest
                or cmd.content is None
                or cmd.revision
                or cmd.digest
            ):
                raise OntologyError("ONTOLOGY_MAINTENANCE_BASE_INVALID")
            self.read_required(call, cmd.ontologyId, cmd.baseRevision)
            base = service.repo.read(scope, cmd.ontologyId, cmd.baseRevision)
            if base["digest"] != cmd.baseDigest:
                raise OntologyError("ONTOLOGY_MAINTENANCE_BASE_INVALID")
        else:
            if (
                not head
                or not cmd.revision
                or not cmd.digest
                or cmd.content is not None
                or cmd.baseRevision
                or cmd.baseDigest
            ):
                raise OntologyError("ONTOLOGY_MAINTENANCE_COMMAND_INVALID")
            self.read_required(call, cmd.ontologyId, cmd.revision)
            selected = service.repo.read(scope, cmd.ontologyId, cmd.revision)
            if selected["digest"] != cmd.digest:
                raise OntologyError("ONTOLOGY_MAINTENANCE_BASE_INVALID")
        revision = cmd.revision or REVISION_PREFIX + canonical_digest(
            [list(scope), actor, cmd.model_dump(mode="json")]
        )
        owner = OntologyCommand(
            request_key=REQUEST_PREFIX + canonical_digest(cmd.commandKey),
            expected_version=cmd.expectedVersion,
            revision_id=revision,
            digest=cmd.digest,
            content=cmd.content,
            reason=cmd.reason,
        )
        target = resource(cmd.ontologyId, revision)
        members = (
            ExactGrant("BUSINESS_ONTOLOGY", cmd.action, target),
            ExactGrant("BUSINESS_ONTOLOGY", "READ", target),
        )
        grants = bound_grants(self.grants, c)
        grants.target_validator = CommandTargets(
            grants.target_validator, call.context, c, members
        )
        proof = ResourceAutomation.decide(
            SimpleNamespace(policy=self.policy, grants=grants),
            call,
            members,
            key + ":" + digest,
            work,
            issuer,
            purpose="ONTOLOGY_MAINTENANCE",
        )
        record = {
            "schemaVersion": SCHEMA,
            "scope": list(scope),
            "actor": actor,
            "ontologyId": cmd.ontologyId,
            "action": cmd.action,
            "generation": call.policy_generation,
            "policyDigest": self.policy.digest,
            "policyDecisionId": proof.decision_id,
            "baseRevision": cmd.baseRevision,
            "baseDigest": cmd.baseDigest,
            "command": cmd.model_dump(mode="json"),
            "ownerCommand": owner.model_dump(mode="json"),
            "expiresAt": min(
                work.expiresAt,
                self.grants.clock() + timedelta(seconds=self.policy.grantTTLSeconds),
            ).isoformat(),
        }
        c.execute(
            "INSERT INTO execution_authority.prepared_resource_commands(namespace,security_domain,actor_id,command_key,digest,result) VALUES(%s,%s,%s,%s,%s,%s)",
            (*scope, actor, key, digest, Jsonb(record)),
        )
        service.handle(cmd.action, cmd.ontologyId, owner.model_dump(mode="json"))
        return self.receipt(call, cmd.commandKey)
