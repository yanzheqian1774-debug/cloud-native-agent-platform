"""Default-closed assembly of the two existing-owner supplement adapters."""

from .authority_contracts import AuthorityError


def operations(planning, services, *, enabled=False, sales_v2_candidate=False):
    if not enabled:
        return ()
    if (
        not planning
        or not services
        or "skill" not in services
        or not sales_v2_candidate
    ):
        raise AuthorityError("SALES_SUPPLEMENT_COMPOSITION_UNAVAILABLE")
    from .planning_sales_supplement import operations as plan_operations
    from .prepared_skill_successor import operations as skill_operations

    return skill_operations(services["skill"]) + plan_operations(planning)
