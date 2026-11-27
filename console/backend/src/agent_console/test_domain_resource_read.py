# ruff: noqa: E501 -- Exact scoped SQL kept together for audit.
"""Explicit test-domain READ of canonical Team/Employee records, not execution."""

from .authority_contracts import AuthenticationSource, AuthorityError
from .digital_employee_definition import digest
from .digital_employee_definition_postgres import PostgresEmployeeDefinitionRepository
from .execution_domain import ScopeIdentity
from .published_test_resources import lineage_block as curated_lineage_block
from .team_definition_postgres import PostgresTeamDefinitionRepository
from .test_resource_read_policy import TestReadTarget


def require(ok):
    if not ok:
        raise AuthorityError("TEST_READ_POLICY_SNAPSHOT_CHANGED")


def require_subject(policy, grants, context, connection):
    if not getattr(policy, "registeredResources", ()):
        return
    if (
        context.authentication_source != AuthenticationSource.BROWSER_SESSION
        or not context.principal_id.startswith("human:")
        or context.scope.tenant_id != policy.tenant
        or context.scope.security_domain != policy.securityDomain
    ):
        raise AuthorityError("TEST_READ_POLICY_SCOPE_DENIED")
    grants.authorization.require_current_context(
        context,
        (policy.targets[0].grant,),
        now=grants.clock(),
        generation=grants.generation.generation,
        recovery_epoch=grants.recovery_epoch,
        connection=connection,
    )
    account = connection.execute(
        "SELECT 1 FROM browser_identity.local_accounts WHERE principal_id=%s "
        "AND tenant_id=%s AND security_domain=%s AND status='ENABLED' FOR SHARE",
        (context.principal_id, context.scope.tenant_id, context.scope.security_domain),
    ).fetchone()
    if not account:
        raise AuthorityError("TEST_READ_POLICY_SCOPE_DENIED")


def select(policy, context, c):
    try:
        return _select(policy, context, c)
    except AuthorityError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthorityError("TEST_READ_POLICY_SNAPSHOT_CHANGED") from exc


def _select(policy, context, c):
    scope = ScopeIdentity(context.scope.tenant_id, context.scope.security_domain)
    targets = []
    for spec in sorted(policy.registeredResources, key=lambda x: x.kind):
        enrolled = [
            r.logicalId for r in policy.enrolledResources if r.kind == spec.kind
        ]
        if spec.kind == "team":
            rows = c.execute(
                "SELECT d.team_id,d.head_revision_id,d.aggregate_version FROM "
                "team_definition.definitions d WHERE namespace=%s AND security_domain=%s "
                "AND ((%s AND team_id=ANY(%s)) OR (%s AND EXISTS(SELECT 1 FROM team_definition.receipts r WHERE r.namespace=d.namespace AND r.security_domain=d.security_domain AND r.team_id=d.team_id AND r.aggregate_version=1 AND r.actor_id=%s))) "
                "ORDER BY team_id LIMIT 129 FOR SHARE",
                (
                    scope.namespace,
                    scope.security_domain,
                    spec.mode == "ISOLATED_TEST_DOMAIN_SHARE",
                    enrolled,
                    spec.mode == "CREATOR_ONLY",
                    context.principal_id,
                ),
            ).fetchall()
            require(len(rows) <= 128)
            for head in rows:
                receipt = c.execute(
                    "SELECT * FROM team_definition.receipts WHERE namespace=%s "
                    "AND security_domain=%s AND team_id=%s AND aggregate_version=1",
                    (scope.namespace, scope.security_domain, head["team_id"]),
                ).fetchall()
                require(len(receipt) == 1)
                root = receipt[0]
                first = PostgresTeamDefinitionRepository.read(
                    c, scope, head["team_id"], root["revision_id"]
                )
                require(first.predecessor_revision_id is None)
                require(
                    root["payload_digest"]
                    == digest(
                        {
                            "revision": first.canonical_record(),
                            "expectedVersion": 0,
                            "actor": root["actor_id"],
                        }
                    )
                )
                require(bool(root["decision_id"]) and bool(root["command_id"]))
                if (
                    spec.mode == "CREATOR_ONLY"
                    and root["actor_id"] != context.principal_id
                ):
                    continue
                current = head["head_revision_id"]
                seen = set()
                while current is not None:
                    require(current not in seen and len(seen) < 256)
                    seen.add(current)
                    revision = PostgresTeamDefinitionRepository.read(
                        c, scope, head["team_id"], current
                    )
                    receipts = c.execute(
                        "SELECT * FROM team_definition.receipts WHERE namespace=%s AND security_domain=%s AND team_id=%s AND revision_id=%s",
                        (
                            scope.namespace,
                            scope.security_domain,
                            head["team_id"],
                            current,
                        ),
                    ).fetchall()
                    require(len(receipts) == 1)
                    receipt = receipts[0]
                    require(
                        receipt["aggregate_version"]
                        == head["aggregate_version"] - len(seen) + 1
                    )
                    require(
                        receipt["payload_digest"]
                        == digest(
                            {
                                "revision": revision.canonical_record(),
                                "expectedVersion": receipt["aggregate_version"] - 1,
                                "actor": receipt["actor_id"],
                            }
                        )
                    )
                    if current == head["head_revision_id"]:
                        selected = revision
                    if current == root["revision_id"]:
                        break
                    current = revision.predecessor_revision_id
                require(
                    current == root["revision_id"]
                    and len(seen) == head["aggregate_version"]
                )
                targets.append(
                    TestReadTarget(
                        owner="TEAM",
                        action="READ",
                        resource=f"team:{head['team_id']}:{selected.revision_id}",
                        digest=selected.content_digest,
                        purpose=spec.purpose,
                    )
                )
        else:
            rows = c.execute(
                "SELECT definition_id,aggregate_version FROM digital_employee_definition.definitions "
                "WHERE namespace=%s AND security_domain=%s AND definition_id=ANY(%s) ORDER BY definition_id LIMIT 129 FOR SHARE",
                (scope.namespace, scope.security_domain, enrolled),
            ).fetchall()
            require(len(rows) <= 128)
            for head in rows:
                identity = head["definition_id"]
                # Shared test domain is explicit policy, never a guessed creator.
                revisions = c.execute(
                    "SELECT revision_id,predecessor_revision_id,digest FROM digital_employee_definition.revisions "
                    "WHERE namespace=%s AND security_domain=%s AND definition_id=%s",
                    (scope.namespace, scope.security_domain, identity),
                ).fetchall()
                require(0 < len(revisions) <= 256)
                by_id = {r["revision_id"]: r for r in revisions}
                facts = c.execute(
                    "SELECT * FROM digital_employee_definition.facts WHERE namespace=%s "
                    "AND security_domain=%s AND definition_id=%s ORDER BY ordinal",
                    (scope.namespace, scope.security_domain, identity),
                ).fetchall()
                require(bool(facts) and facts[0]["action"] == "CREATE")
                canonical = {}
                for revision_id, stored in by_id.items():
                    value = PostgresEmployeeDefinitionRepository._read(
                        c, scope, identity, revision_id
                    )
                    record = value["revision"]
                    require(
                        (
                            record["namespace"],
                            record["securityDomain"],
                            record["definitionId"],
                            record["revisionId"],
                            value["digest"],
                        )
                        == (
                            scope.namespace,
                            scope.security_domain,
                            identity,
                            revision_id,
                            stored["digest"],
                        )
                    )
                    require(
                        record.get("predecessorRevisionId")
                        == stored["predecessor_revision_id"]
                    )
                    canonical[revision_id] = value
                for ordinal, fact in enumerate(facts, 1):
                    require(
                        fact["ordinal"] == ordinal
                        and fact["revision_id"] in by_id
                        and fact["revision_digest"]
                        == by_id[fact["revision_id"]]["digest"]
                    )
                    expected = (
                        [
                            canonical[fact["revision_id"]]["revision"],
                            ordinal - 1,
                            fact["decision_id"],
                            "CREATE",
                        ]
                        if fact["action"] == "CREATE"
                        else [
                            identity,
                            fact["revision_id"],
                            fact["revision_digest"],
                            fact["action"],
                            ordinal - 1,
                            fact["decision_id"],
                        ]
                    )
                    require(fact["payload_digest"] == digest(expected))
                created = [f for f in facts if f["action"] == "CREATE"]
                require(
                    {f["revision_id"] for f in created} == set(by_id)
                    and len(created) == len(by_id)
                )
                require(
                    bool(created) and facts[-1]["ordinal"] == head["aggregate_version"]
                )
                selected_ids = {created[-1]["revision_id"]}
                publications = [f for f in facts if f["action"] == "PUBLISH"]
                if publications:
                    selected_ids.add(publications[-1]["revision_id"])
                for selected_id in sorted(selected_ids):
                    seen = set()
                    current = selected_id
                    while current is not None:
                        require(current in by_id and current not in seen)
                        seen.add(current)
                        value = PostgresEmployeeDefinitionRepository._read(
                            c, scope, identity, current
                        )
                        record = value["revision"]
                        require(
                            (
                                record["namespace"],
                                record["securityDomain"],
                                record["definitionId"],
                                record["revisionId"],
                                value["digest"],
                            )
                            == (
                                scope.namespace,
                                scope.security_domain,
                                identity,
                                current,
                                by_id[current]["digest"],
                            )
                        )
                        require(
                            record.get("predecessorRevisionId")
                            == by_id[current]["predecessor_revision_id"]
                        )
                        if current == selected_id:
                            selected = value
                        current = by_id[current]["predecessor_revision_id"]
                    targets.append(
                        TestReadTarget(
                            owner="EMPLOYEE",
                            action="READ",
                            resource=f"employee:{identity}:{selected_id}",
                            digest=selected["digest"],
                            purpose=spec.purpose,
                        )
                    )
    return tuple(targets)


def lineage_block(c, context, target, policy, generation):
    kind = "team" if target.owner == "TEAM" else "employee"
    if not any(s.kind == kind for s in policy.registeredResources):
        return curated_lineage_block(c, context, target.resource, policy, generation)
    table, key, prefix = (
        ("team_definition.revisions", "team_id", "team:")
        if kind == "team"
        else ("digital_employee_definition.revisions", "definition_id", "employee:")
    )
    scope = (context.scope.tenant_id, context.scope.security_domain)
    found = c.execute(
        f"SELECT {key} identity FROM {table} WHERE namespace=%s AND security_domain=%s AND %s || {key} || ':' || revision_id=%s",
        (*scope, prefix, target.resource),
    ).fetchone()
    require(found)
    rows = c.execute(
        f"SELECT revision_id FROM {table} WHERE namespace=%s AND security_domain=%s AND {key}=%s",
        (*scope, found["identity"]),
    ).fetchall()
    refs = [prefix + found["identity"] + ":" + r["revision_id"] for r in rows]
    known, same = set(), set()
    for identity in (*generation.credentials, *generation.local_accounts):
        ids = {
            identity.credential_id,
            getattr(identity, "grant_source_id", identity.credential_id),
        }
        known.update(ids)
        if (
            identity.principal_id == context.principal_id
            and identity.scope == context.scope
        ):
            same.update(ids)
    revoked = {
        identity
        for identity, grant in generation.static_grant_revocation_tombstones
        if grant.owner == target.owner
        and grant.action == "READ"
        and grant.exact_resource in refs
    }
    if revoked - known:
        raise AuthorityError("TEST_READ_LINEAGE_IDENTITY_UNVERIFIED")
    if revoked & same:
        return "REVOKED"
    args = (*scope, context.principal_id, target.owner, refs)
    if c.execute(
        "SELECT 1 FROM authorization_admin.grants g JOIN authorization_admin.grant_revocation_facts f USING(grant_id) WHERE g.tenant_id=%s AND g.security_domain=%s AND g.subject_principal_id=%s AND g.owner=%s AND g.action='READ' AND g.exact_resource=ANY(%s) LIMIT 1",
        args,
    ).fetchone():
        return "REVOKED"
    if c.execute(
        "SELECT 1 FROM authorization_admin.grant_requests r JOIN authorization_admin.grant_request_members m USING(request_id) WHERE r.tenant_id=%s AND r.security_domain=%s AND r.subject_principal_id=%s AND m.owner=%s AND m.action='READ' AND m.exact_resource=ANY(%s) AND r.state='REJECTED' LIMIT 1",
        args,
    ).fetchone():
        return "DENIED"
    return None
