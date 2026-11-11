"""Consolidated declarative change preview; never global impact or execution proof."""

from .business_capability import BusinessCapabilityError
from .digital_employee_definition import digest

_FIELDS = (
    "title",
    "intent",
    "inputs",
    "outputs",
    "business_scope",
    "exclusions",
    "manual_involvement",
    "acceptance_criteria",
    "known_limitations",
    "origin",
)


def change_preview(revision, previous, *, aggregate_version, generation):
    current = revision.canonical_record()
    before = previous.canonical_record() if previous else {}
    changes = [
        {"field": field, "before": before.get(field), "after": current[field]}
        for field in _FIELDS
        if before.get(field) != current[field]
    ]
    old = (
        {(b.kind, b.reference.resource_id): b for b in previous.bindings}
        if previous
        else {}
    )
    new = {(b.kind, b.reference.resource_id): b for b in revision.bindings}
    bindings = []
    for key in sorted(old.keys() | new.keys()):
        left, right = old.get(key), new.get(key)
        if left == right:
            continue
        from dataclasses import asdict

        bindings.append(
            {
                "kind": key[0],
                "resourceId": key[1],
                "before": asdict(left) if left else None,
                "after": asdict(right) if right else None,
            }
        )
    record = {
        "schemaVersion": "business-capability-change.v1",
        "capabilityId": revision.capability_id,
        "revisionId": revision.revision_id,
        "revisionDigest": revision.content_digest,
        "previousPublishedRevisionId": previous.revision_id if previous else None,
        "previousPublishedDigest": previous.content_digest if previous else None,
        "aggregateVersion": aggregate_version,
        "authorityGeneration": generation,
        "fieldChanges": changes,
        "bindingChanges": bindings,
        "impactScope": "CAPABILITY_DEFINITION_ONLY",
        "automaticReferenceUpdates": False,
        "executionAuthorized": False,
        "validationScope": "DECLARATIVE_FIXED_BINDINGS_NOT_SAMPLE_EXECUTION",
    }
    return {**record, "impactDigest": digest(record)}


def verify_review(command, preview):
    if command.expectedVersion != preview["aggregateVersion"]:
        raise BusinessCapabilityError("CAPABILITY_VERSION_CONFLICT")
    if command.digest != preview["revisionDigest"]:
        raise BusinessCapabilityError("CAPABILITY_REVISION_MISMATCH")
    if command.impactDigest != preview["impactDigest"]:
        raise BusinessCapabilityError("CAPABILITY_IMPACT_CHANGED")
