"""Build exact selected successors; no persistence, authorization, or publication.

The transaction coordinator must separately check current heads, existing drafts,
permissions and publication prerequisites. These builders never select latest.
"""

from dataclasses import dataclass, replace

from .business_capability import FixedReference
from .execution_domain import ScopeIdentity


class UpgradeSelectionError(ValueError):
    pass


@dataclass(frozen=True)
class SelectedReplacement:
    scope: ScopeIdentity
    kind: str
    before: FixedReference
    after: FixedReference

    def __post_init__(self):
        if not isinstance(self.scope, ScopeIdentity) or self.kind not in {
            "SKILL",
            "EMPLOYEE",
        }:
            raise UpgradeSelectionError("UPGRADE_SELECTION_KIND_OR_SCOPE_INVALID")
        if not isinstance(self.before, FixedReference) or not isinstance(
            self.after, FixedReference
        ):
            raise UpgradeSelectionError("UPGRADE_EXACT_REFERENCES_REQUIRED")
        if self.before.resource_id != self.after.resource_id:
            raise UpgradeSelectionError("UPGRADE_RESOURCE_IDENTITY_CHANGED")
        if self.before.revision_id == self.after.revision_id:
            raise UpgradeSelectionError("UPGRADE_NEW_REVISION_REQUIRED")


def _selection(scope, replacements):
    if not 1 <= len(replacements) <= 64:
        raise UpgradeSelectionError("UPGRADE_SELECTION_LIMIT")
    result = {}
    for item in replacements:
        if not isinstance(item, SelectedReplacement) or item.scope != scope:
            raise UpgradeSelectionError("UPGRADE_SCOPE_MISMATCH")
        key = (item.kind, item.before.resource_id)
        if key in result:
            raise UpgradeSelectionError("UPGRADE_DUPLICATE_SELECTION")
        result[key] = item
    return result


def _reference(kind, current, selected):
    item = selected.get((kind, current.resource_id))
    if item is None:
        return current
    if current != item.before:
        raise UpgradeSelectionError("UPGRADE_ORIGINAL_REFERENCE_MISMATCH")
    return item.after


def employee_successor(original, revision_id, replacements):
    selected = _selection(original.scope, replacements)

    def update_member(member):
        ref = _reference(
            member.kind,
            FixedReference(member.resource_id, member.revision_id, member.digest),
            selected,
        )
        return replace(member, revision_id=ref.revision_id, digest=ref.digest)

    members = tuple(update_member(member) for member in original.members)
    if members == original.members:
        raise UpgradeSelectionError("UPGRADE_NO_SELECTED_REFERENCE")
    mapping = dict(zip(original.members, members, strict=True))
    return replace(
        original,
        revision_id=revision_id,
        predecessor_revision_id=original.revision_id,
        members=members,
        responsibility_bindings=tuple(
            replace(binding, member=mapping[binding.member])
            for binding in original.responsibility_bindings
        ),
        responsibility_bindings_explicit=True,
    )


def capability_successor(original, revision_id, replacements):
    selected = _selection(original.scope, replacements)
    bindings = tuple(
        replace(b, reference=_reference(b.kind, b.reference, selected))
        for b in original.bindings
    )
    if bindings == original.bindings:
        raise UpgradeSelectionError("UPGRADE_NO_SELECTED_REFERENCE")
    return replace(
        original,
        revision_id=revision_id,
        predecessor_revision_id=original.revision_id,
        bindings=bindings,
    )
