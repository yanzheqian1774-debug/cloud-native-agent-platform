"""Authorization-scoped traceability derived from existing resource facts."""

from typing import Any

from agent_console.product_evidence_schemas import (
    ProductClaim,
    TechnicalFact,
    TraceabilityDTO,
    TraceabilityEvidence,
    TraceabilitySubject,
)
from agent_console.resource_catalog_service import (
    ProductAssemblyFailure,
    ProductScope,
    ResourceCatalogService,
)


class ProductEvidenceService:
    """Map authorized facts without creating Evidence or persistence authority."""

    def __init__(self, catalog: ResourceCatalogService) -> None:
        self.catalog = catalog

    def get(
        self,
        scope: ProductScope,
        kind: str,
        resource_id: str,
        revision_id: str,
        digest: str,
    ) -> TraceabilityDTO:
        try:
            resource = self.catalog.get(scope, kind, resource_id)
        except ProductAssemblyFailure as exc:
            if exc.status == 404:
                raise ProductAssemblyFailure("PRODUCT_CONTEXT_NOT_FOUND", 404) from exc
            raise
        if (
            not revision_id
            or not digest
            or resource.get("revisionId") != revision_id
            or resource.get("digest") != digest
        ):
            raise ProductAssemblyFailure("PRODUCT_CONTEXT_NOT_FOUND", 404)

        subject = TraceabilitySubject(
            kind=resource["kind"],
            resourceId=resource["identity"],
            revisionId=revision_id,
            digest=digest,
        )
        evidence = self._evidence(subject, resource.get("traceabilitySources", {}))
        facts = self._facts(resource)
        claims = self._claims(resource, evidence, facts)
        return TraceabilityDTO(
            subject=subject, claims=claims, evidence=evidence, technicalFacts=facts
        )

    @staticmethod
    def _evidence(
        subject: TraceabilitySubject, sources: dict[str, Any]
    ) -> list[TraceabilityEvidence]:
        mapped: list[TraceabilityEvidence] = []
        for review in sources.get("reviews", []):
            mapped.append(
                TraceabilityEvidence(
                    evidenceId=review["reviewId"],
                    evidenceType="HUMAN_REVIEW",
                    subject=subject,
                    provenance={
                        "authority": "RESOURCE_LIFECYCLE_REPOSITORY",
                        "decision": review.get("decision"),
                        "actor": review.get("actor"),
                    },
                    observedAt=review.get("reviewedAt"),
                )
            )
        for key, evidence_type, identity_key, observed_key in (
            ("citations", "CITATION", "citationId", "recordedAt"),
            ("discoverySnapshots", "DISCOVERY_SNAPSHOT", "snapshotId", "discoveredAt"),
            ("invocations", "INVOCATION", "invocationId", "recordedAt"),
        ):
            for item in sources.get(key, []):
                evidence_id = item.get(identity_key)
                if not evidence_id:
                    continue
                mapped.append(
                    TraceabilityEvidence(
                        evidenceId=evidence_id,
                        evidenceType=evidence_type,
                        subject=subject,
                        provenance={
                            "authority": "RESOURCE_DOMAIN_REPOSITORY",
                            "sourceType": key,
                        },
                        observedAt=item.get(observed_key),
                    )
                )
        return mapped

    @staticmethod
    def _facts(resource: dict[str, Any]) -> list[TechnicalFact]:
        claims = ["resource.exact-reference", "resource.lifecycle"]
        steps = ["inspect-resource"]
        facts = [
            TechnicalFact(
                factKey="resource.exact-reference",
                valueClassification="EXACT_BACKEND_FACT",
                provenance={
                    "authority": "RESOURCE_DOMAIN_REPOSITORY",
                    "kind": resource["kind"],
                    "resourceId": resource["identity"],
                    "revisionId": resource["revisionId"],
                    "digest": resource["digest"],
                },
                affectedClaimKeys=["resource.exact-reference"],
                affectedBusinessStepIds=steps,
            ),
            TechnicalFact(
                factKey="resource.lifecycle",
                valueClassification="BACKEND_OBSERVED_STATE",
                provenance={
                    "authority": "RESOURCE_DOMAIN_REPOSITORY",
                    "lifecycleStatus": resource["lifecycleStatus"],
                    "reviewStatus": resource["reviewStatus"],
                },
                affectedClaimKeys=claims[1:],
                affectedBusinessStepIds=["govern-resource"],
            ),
        ]
        if resource.get("relationships"):
            facts.append(
                TechnicalFact(
                    factKey="resource.relationships",
                    valueClassification="DERIVED_EXACT_REFERENCES",
                    provenance={
                        "authority": "RESOURCE_DOMAIN_REPOSITORIES",
                        "relationshipCount": len(resource["relationships"]),
                        "exactReferences": resource["relationships"],
                    },
                    affectedClaimKeys=["resource.composition"],
                    affectedBusinessStepIds=["compose-resource"],
                )
            )
        return facts

    @staticmethod
    def _claims(
        resource: dict[str, Any],
        evidence: list[TraceabilityEvidence],
        facts: list[TechnicalFact],
    ) -> list[ProductClaim]:
        review_ids = [
            item.evidenceId for item in evidence if item.evidenceType == "HUMAN_REVIEW"
        ]
        governed = (
            resource["lifecycleStatus"] == "PUBLISHED"
            and resource["reviewStatus"] == "APPROVED"
            and bool(review_ids)
        )
        claims = [
            ProductClaim(
                claimKey="resource.exact-reference",
                productLabel="Exact resource revision",
                status="SUPPORTED",
                technicalFactKeys=["resource.exact-reference"],
                affectedBusinessStepIds=["inspect-resource"],
            ),
            ProductClaim(
                claimKey="resource.lifecycle",
                productLabel="Published and review-backed",
                status="SUPPORTED" if governed else "UNSUPPORTED",
                limitationCodes=[] if governed else ["REVIEW_OR_PUBLICATION_REQUIRED"],
                evidenceRefs=review_ids,
                technicalFactKeys=["resource.lifecycle"],
                affectedBusinessStepIds=["govern-resource"],
            ),
        ]
        if any(item.factKey == "resource.relationships" for item in facts):
            claims.append(
                ProductClaim(
                    claimKey="resource.composition",
                    productLabel="Uses exact governed resource references",
                    status="SUPPORTED",
                    technicalFactKeys=["resource.relationships"],
                    affectedBusinessStepIds=["compose-resource"],
                )
            )
        if resource["kind"] == "RUNTIME_PROFILE":
            claims.append(
                ProductClaim(
                    claimKey="runtime.execution",
                    productLabel="Runtime can execute",
                    status="UNSUPPORTED",
                    limitationCodes=["DECLARATION_ONLY", "NO_EXECUTION_AUTHORITY"],
                    technicalFactKeys=["resource.exact-reference"],
                    affectedBusinessStepIds=["declare-runtime-requirements"],
                )
            )
        if any(item.get("targetKind") == "MODEL" for item in resource["relationships"]):
            claims.append(
                ProductClaim(
                    claimKey="model.verified",
                    productLabel="Model reference is verified",
                    status="UNSUPPORTED",
                    limitationCodes=["UNVERIFIED_MODEL_REFERENCE"],
                    technicalFactKeys=["resource.relationships"],
                    affectedBusinessStepIds=["compose-resource"],
                )
            )
        return claims
