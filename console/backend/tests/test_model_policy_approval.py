import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from agent_console.model_policy_approval import DEADLINE, ModelPublicationPolicy, digest


def verification_files(pin, *, model, profile, provider, standing, source):
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    artifact = pin("schema.json", schema)
    code = pin("verified-code.json", {"fixture": "controlled registered adapter"})
    report = pin(
        "verification.json",
        dict(
            status="PASS_OFFLINE_ONLY",
            modelDigest=model,
            connectionProfileDigest=profile,
            adapterPolicyDigest="d" * 64,
            schemaDigest=digest(schema),
            provider=provider,
            standingAuthorizationDigest=standing["sha256"],
            sourcePolicyDigest=source["sha256"],
            sameOriginalBudget=True,
            modelCalled=False,
            sourceFiles=[code],
        ),
    )
    return dict(
        provider=provider,
        codeVerification=report,
        schemaArtifact=artifact,
        schemaDigest=digest(schema),
    )


def policy_document(tmp_path):
    def pin(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value))
        return dict(path=str(path), sha256=sha256(path.read_bytes()).hexdigest())

    standing = pin(
        "standing.json",
        dict(
            doesNotAssertIndividualReview=True,
            budgetIncreaseAuthorized=False,
            externalBusinessWritesAuthorized=False,
        ),
    )
    source = pin(
        "sources.json", dict(source="existing-exact-source", externalWrites=False)
    )
    proof = verification_files(
        pin,
        model="b" * 64,
        profile="c" * 64,
        provider=dict(
            providerId="provider",
            revisionId="7",
            digest="a" * 64,
            adapterContractId="adapter",
            adapterContractRevisionId="7",
        ),
        standing=standing,
        source=source,
    )
    evidence = pin(
        "candidate.json",
        dict(
            modelDigest="b" * 64,
            profileDigest="c" * 64,
            adapterDigest="d" * 64,
            schemaDigest=proof["schemaDigest"],
            codeVerificationDigest=proof["codeVerification"]["sha256"],
            sourcePolicyDigest=source["sha256"],
            validationState="PASSED",
            externalWrites=False,
        ),
    )
    return dict(
        schemaVersion="model-standing-publication.v1",
        enabled=True,
        policyId="bounded",
        policyVersion="1",
        namespace="tenant",
        securityDomain="domain",
        publisherId="human:alice",
        nativeModel="gpt-6.1-sol",
        purpose="F3_ORIGINAL_CONVERSATION_CLOSURE",
        baseline=dict(modelId="model", revisionId="6", digest="a" * 64),
        candidate=dict(modelId="model", revisionId="7", digest="b" * 64),
        profileDigest="c" * 64,
        adapterDigest="d" * 64,
        **proof,
        standingAuthorization=standing,
        sourcePolicy=source,
        candidateEvidence=evidence,
        ledgerId="existing",
        allowanceId="existing",
        allowanceDigest="f" * 64,
        cumulativeCallCap=100,
        cumulativeCostMicrousd=10000000,
        expiresAt=DEADLINE.isoformat(),
        externalWrites=False,
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("cumulativeCallCap", 101),
        ("cumulativeCostMicrousd", 10000001),
        ("externalWrites", True),
        ("nativeModel", "other"),
        ("expiresAt", (DEADLINE + timedelta(seconds=1)).isoformat()),
    ],
)
def test_no_scope_or_budget_expansion(tmp_path, key, value):
    data = policy_document(tmp_path)
    data[key] = value
    with pytest.raises((ValueError, RuntimeError)):
        ModelPublicationPolicy.model_validate(data)


def test_standing_is_not_individual_review_and_pins_changed_evidence(tmp_path):
    data = policy_document(tmp_path)
    value = ModelPublicationPolicy.model_validate(data)
    assert (
        value.evidence()["standingAuthorizationDigest"]
        == data["standingAuthorization"]["sha256"]
    )
    from pathlib import Path

    Path(data["sourcePolicy"]["path"]).write_text("{}")
    with pytest.raises(RuntimeError, match="EVIDENCE_CHANGED"):
        value.evidence()


def test_default_off_and_exact_candidate(tmp_path):
    data = policy_document(tmp_path)
    data.pop("enabled")
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    with pytest.raises(RuntimeError, match="DISABLED"):
        ModelPublicationPolicy.load(path)
    assert datetime.now(UTC).tzinfo is not None


def test_policy_requires_private_absolute_non_symlink_file(tmp_path):
    data = policy_document(tmp_path)
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(data))
    path.chmod(0o644)
    with pytest.raises(RuntimeError, match="PRIVATE_POLICY_REQUIRED"):
        ModelPublicationPolicy.load(path)
    path.chmod(0o600)
    assert ModelPublicationPolicy.load(path).enabled
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(RuntimeError, match="PRIVATE_POLICY_REQUIRED"):
        ModelPublicationPolicy.load(link)


def test_code_and_schema_pins_are_rechecked(tmp_path):
    from pathlib import Path

    data = policy_document(tmp_path)
    policy = ModelPublicationPolicy.model_validate(data)
    policy.evidence()
    report = json.loads(Path(data["codeVerification"]["path"]).read_text())
    code = Path(report["sourceFiles"][0]["path"])
    original = code.read_bytes()
    code.write_text('{"changed":true}')
    with pytest.raises(RuntimeError, match="EVIDENCE_CHANGED"):
        policy.evidence()
    code.write_bytes(original)
    Path(data["schemaArtifact"]["path"]).write_text('{"type":"string"}')
    with pytest.raises(RuntimeError, match="EVIDENCE_CHANGED"):
        policy.evidence()
