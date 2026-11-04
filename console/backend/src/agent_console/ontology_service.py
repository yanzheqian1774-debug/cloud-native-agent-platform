"""Ontology owner application, always called inside the existing authorization UoW."""

import json

from .ontology_domain import OntologyCommand, OntologyContent, OntologyError
from .ontology_postgres import PostgresOntologyRepository
from .ontology_query import SemanticQuery, query_sales
from .prepared_execution_resources import published
from .resource_use_domain import canonical_digest
from .workbench_business_problem import OwnerPrincipal


def resource(identity, revision):
    return f"business-ontology:{identity}:{revision}"


class OntologyService:
    def __init__(self, call):
        self.call = call
        self.repo = PostgresOntologyRepository(call.connection)
        self.scope = (call.context.scope.tenant_id, call.context.scope.security_domain)
        self.actor = call.context.principal_id
        self.principal = OwnerPrincipal(self.actor, *self.scope)

    def dependencies(self, content):
        from .execution_domain import ScopeIdentity

        scope = ScopeIdentity(*self.scope)
        sources = []
        for mapping in content.mappings:
            ref = mapping.source
            self.call.authority.require(
                self.principal,
                "KNOWLEDGE",
                "READ_RESOURCE",
                f"knowledge:prepared-resource:{ref.resource_id}:{ref.revision_id}",
            )
            value = published(self.call.connection, scope, "KNOWLEDGE", ref)
            docs = value.get("documents", [])
            if len(docs) != 1 or len(docs[0].get("chunks", [])) != 1:
                raise OntologyError("ONTOLOGY_SINGLE_SOURCE_REQUIRED")
            raw = docs[0]["chunks"][0]["content"]
            import hashlib

            if hashlib.sha256(raw.encode()).hexdigest() != docs[0]["contentDigest"]:
                raise OntologyError("ONTOLOGY_SOURCE_CORRUPT")
            source = json.loads(raw)
            if mapping.source_digest != canonical_digest(source):
                raise OntologyError("ONTOLOGY_SOURCE_DIGEST_MISMATCH")
            sources.append(source)
        for action in content.actions:
            ref = action.skill
            self.call.authority.require(
                self.principal,
                "SKILL",
                "READ_RESOURCE",
                f"skill-invocation:prepared-resource:{ref.resource_id}:{ref.revision_id}",
            )
            skill = published(self.call.connection, scope, "SKILL", ref)
            operations = skill.get("operations", [])
            if not any(
                (
                    op.get("name"),
                    op.get("executorId"),
                    op.get("executorRevision"),
                    op.get("executorConfigurationDigest"),
                    op.get("sideEffectClass"),
                )
                == (
                    action.operation,
                    action.executor_id,
                    action.executor_revision,
                    action.executor_digest,
                    "READ_ONLY",
                )
                for op in operations
            ):
                raise OntologyError("ONTOLOGY_SKILL_CONTRACT_MISMATCH")
        return sources

    def handle(self, action, identity, payload):
        command = OntologyCommand.model_validate(payload)
        self.call.authority.require(
            self.principal,
            "BUSINESS_ONTOLOGY",
            action,
            resource(identity, command.revision_id),
        )
        if action in {"CREATE", "REVISE"}:
            content = command.content
            if content is None:
                raise OntologyError("ONTOLOGY_CONTENT_REQUIRED")
        else:
            record = self.repo.read(self.scope, identity, command.revision_id)
            content = OntologyContent.model_validate(record["content"])
        sources = self.dependencies(content)
        evidence = None
        if action == "TEST":
            checks = []
            for source in sources:
                for metric in content.metrics:
                    result = query_sales(
                        content, source, SemanticQuery(metric=metric.code)
                    )
                    checks.append(
                        {
                            "metric": metric.code,
                            "source_digest": canonical_digest(source),
                            "result_digest": canonical_digest(result),
                        }
                    )
            evidence = checks
        return self.repo.command(
            self.scope, self.actor, identity, action, command, evidence=evidence
        )
