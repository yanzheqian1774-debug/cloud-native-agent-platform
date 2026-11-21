# ruff: noqa: F401,F811 -- Real isolated formal-owner fixture graph.
from dataclasses import replace

import pytest
from agent_console.authority_configuration import LocalAccountBinding
from agent_console.authority_contracts import AuthorityError, CredentialId
from agent_console.published_test_resources import lineage_block, select
from agent_console.test_resource_read_policy import (
    PublishedMcpTestReadPolicy,
    PublishedTestReadPolicy,
    TestReadPolicy,
)
from pydantic import ValidationError
from test_mcp_tool_test_postgres import (
    automation,
    case,
    live,
    manager,
    repository,
    services,
)
from test_test_resource_read_policy import policy


def selector(kind, name):
    return dict(
        kind=kind,
        logicalId=f"{kind}-definition:{name}",
        anchorRevision="r1",
        anchorDigest="a" * 64,
        purpose="RESOURCE_PREPARATION",
    )


def test_v3_is_explicit_bounded_and_keeps_old_versions(tmp_path):
    old = policy().model_dump(mode="json")
    specs = [selector("skill", "s"), selector("employee", "e"), selector("mcp", "m")]
    v3 = PublishedMcpTestReadPolicy.model_validate(
        old
        | dict(schemaVersion="test-resource-read-policy.v3", publishedResources=specs)
    )
    path = tmp_path / "policy.json"
    path.write_text(v3.model_dump_json())
    assert type(TestReadPolicy.load(path)) is PublishedMcpTestReadPolicy
    for bad in [
        [*specs, selector("mcp", "n")],
        [specs[2], selector("mcp", "n")],
        [specs[0]] * 2,
        [selector("skill", str(i)) for i in range(3)],
    ]:
        with pytest.raises(ValidationError):
            PublishedMcpTestReadPolicy.model_validate(
                old
                | dict(
                    schemaVersion="test-resource-read-policy.v3", publishedResources=bad
                )
            )
    for bad in [specs, [specs[2]]]:
        with pytest.raises(ValidationError):
            PublishedTestReadPolicy.model_validate(
                old
                | dict(
                    schemaVersion="test-resource-read-policy.v2", publishedResources=bad
                )
            )
    for version, cls in [("v1", TestReadPolicy), ("v2", PublishedTestReadPolicy)]:
        value = cls.model_validate(
            old | dict(schemaVersion="test-resource-read-policy." + version)
        )
        path.write_text(value.model_dump_json())
        loaded = TestReadPolicy.load(path)
        assert type(loaded) is cls and loaded.digest == value.digest


def test_published_mcp_exact_reference_and_all_identity_tombstones(live):
    _, owner, binding, _, calls, _, _, a, sessions, secret = live
    _, context = sessions.authenticate_session(secret.value)
    p = PublishedMcpTestReadPolicy.model_validate(
        policy().model_dump(mode="json")
        | dict(
            schemaVersion="test-resource-read-policy.v3",
            publishedResources=[
                dict(
                    kind="mcp",
                    logicalId=binding.mcp.resource_id,
                    anchorRevision=binding.mcp.revision_id,
                    anchorDigest=binding.mcp.digest,
                    purpose="RESOURCE_PREPARATION",
                )
            ],
        )
    )
    g = owner.grants.generation
    source = next(
        x
        for x in g.credentials
        if x.principal_id == context.principal_id and x.scope == context.scope
    )
    with a.authority.connection_scope() as c:
        selected = select(c, context, p.publishedResources[0])
        assert (
            selected.resource
            == "skill-invocation:prepared-mcp:prepared-resource:"
            + binding.mcp.resource_id
            + ":"
            + binding.mcp.revision_id
        )
        assert selected.digest == binding.mcp.digest
        assert lineage_block(c, context, selected.resource, p, g) is None
        local_id = CredentialId("local-account:mcp-read-fixture")
        local = LocalAccountBinding(
            local_id,
            "mcp-read-fixture",
            context.principal_id,
            context.scope,
            source.credential_id,
            (),
        )
        for identity in (local_id, source.credential_id):
            denied = replace(
                g,
                local_accounts=(*g.local_accounts, local),
                static_grant_revocation_tombstones=g.static_grant_revocation_tombstones
                | frozenset({(identity, selected.grant)}),
            )
            assert lineage_block(c, context, selected.resource, p, denied) == "REVOKED"
        orphan = replace(
            g,
            static_grant_revocation_tombstones=g.static_grant_revocation_tombstones
            | frozenset({(CredentialId("removed:mcp-unknown"), selected.grant)}),
        )
        with pytest.raises(AuthorityError, match="LINEAGE_IDENTITY_UNVERIFIED"):
            lineage_block(c, context, selected.resource, p, orphan)
        other = replace(
            source,
            credential_id=CredentialId("credential:other-mcp"),
            principal_id="human:other-mcp",
        )
        unrelated = replace(
            g,
            credentials=(*g.credentials, other),
            static_grant_revocation_tombstones=g.static_grant_revocation_tombstones
            | frozenset({(other.credential_id, selected.grant)}),
        )
        assert lineage_block(c, context, selected.resource, p, unrelated) is None
    assert calls == []


def test_v3_formal_read_preparation_follows_only_published_mcp_successor(live):
    from agent_console.ontology_published_read import resolve
    from agent_console.test_resource_read_access import prepare
    from test_mcp_tool_test_postgres import command, replace_namespace

    _, owner, b, _, calls, _, _, a, sessions, secret = live
    _, context = sessions.authenticate_session(secret.value)
    p = PublishedMcpTestReadPolicy.model_validate(
        policy().model_dump(mode="json")
        | dict(
            schemaVersion="test-resource-read-policy.v3",
            enabled=True,
            tenant=b.namespace,
            securityDomain=b.securityDomain,
            subjects=[b.subject],
            issuer=owner.manager.policy.issuer,
            credentialPath=owner.manager.policy.credentialPath,
            expiresAt=b.expiresAt,
            grantTTLSeconds=120,
            targets=[
                dict(
                    owner="SKILL",
                    action="READ_RESOURCE",
                    resource="skill-invocation:prepared-mcp:prepared-resource:"
                    + b.mcp.resource_id
                    + ":"
                    + b.mcp.revision_id,
                    digest=b.mcp.digest,
                    purpose="RESOURCE_PREPARATION",
                )
            ],
            publishedResources=[
                dict(
                    kind="mcp",
                    logicalId=b.mcp.resource_id,
                    anchorRevision=b.mcp.revision_id,
                    anchorDigest=b.mcp.digest,
                    purpose="RESOURCE_PREPARATION",
                )
            ],
        )
    )
    pair = (replace_namespace(a, subject=context), owner.manager)
    svc = owner.manager.services["mcp"]
    record = svc.repository.get(
        svc.scope(b.namespace, b.securityDomain), "mcp", b.mcp.resource_id
    )
    draft = command(
        pair,
        "successor",
        kind="mcp",
        key="curated-mcp-draft",
        identity=b.mcp.resource_id,
        expectedVersion=record["aggregateVersion"],
    )["resource"]
    with a.authority.connection_scope() as c:
        before = resolve(p, context, c)
        assert before.targets[0].digest == b.mcp.digest
    published = command(
        pair,
        "publish",
        kind="mcp",
        key="curated-mcp-publish",
        identity=b.mcp.resource_id,
        expectedVersion=draft["aggregateVersion"],
    )["resource"]
    with a.authority.connection_scope() as c:
        selected = resolve(p, context, c)
        target = selected.targets[0]
        assert target.resource.endswith(":" + published["publishedRevisionId"])
        assert target.resource != before.targets[0].resource
        prepare(
            p,
            owner.grants,
            context,
            c,
            "published:" + selected.digest + ":mcp-successor",
            selected.digest,
        )
    with a.authority.connection_scope() as c:
        assert owner.grants.authorization.has_current_grants(
            context,
            (target.grant,),
            connection=c,
            now=owner.grants.clock(),
            generation=owner.grants.generation.generation,
            recovery_epoch=owner.grants.recovery_epoch,
        )
        assert c.execute(
            "SELECT 1 FROM authorization_admin.grant_decisions "
            "WHERE basis_type='POLICY'"
        ).fetchone()
    assert calls == []
