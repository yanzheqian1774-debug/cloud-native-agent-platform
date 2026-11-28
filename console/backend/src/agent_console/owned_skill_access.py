"""Read-only navigation hints; existing access commands decide authorization."""

from .authority_contracts import AuthorityError
from .workbench_prepared_resources import reference


def access_candidates(call, manager, identity, service, scope, principal):
    """Expose only creator-owned current Skill tuples with current exact READ."""
    if not identity or not manager.owned(call, "skill", identity):
        return []
    record = service.repository.get(scope, "skill", identity)
    current = {
        record.get("currentDraftRevisionId"),
        record.get("publishedRevisionId"),
    } - {None}
    candidates = []
    for revision in record["revisions"]:
        if revision["revisionId"] not in current:
            continue
        try:
            call.authority.require(
                principal,
                "SKILL",
                "READ_RESOURCE",
                reference("skill", identity, revision["revisionId"]),
            )
        except AuthorityError:
            continue
        candidates.append(
            {
                "kind": "skill",
                "identity": identity,
                "revisionId": revision["revisionId"],
                "digest": revision["digest"],
            }
        )
    return candidates
