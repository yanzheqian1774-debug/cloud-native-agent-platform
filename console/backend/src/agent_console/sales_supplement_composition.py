"""Default-closed writes with same-authority historical receipt readers."""

from .authority_contracts import AuthorityError


def operations(planning, services, *, enabled=False, sales_v2_candidate=False):
    complete = planning and services and "skill" in services
    if not enabled and not complete:
        return ()
    if enabled and (not complete or not sales_v2_candidate):
        raise AuthorityError("SALES_SUPPLEMENT_COMPOSITION_UNAVAILABLE")
    from .planning_sales_supplement import operations as plan_operations
    from .prepared_skill_successor import operations as skill_operations

    routes = skill_operations(services["skill"]) + plan_operations(planning)
    return routes if enabled else tuple(r for r in routes if r.method == "GET")
