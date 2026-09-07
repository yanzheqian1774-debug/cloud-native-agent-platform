import pytest
from agent_console.skill_executor import HttpReadOnlySkillExecutor
from agent_console.skill_invocation_domain import (
    SideEffectClass,
    SideEffectPolicy,
    SkillInvocationError,
    SkillIOLimits,
)


def test_io_limits_are_named_versioned_and_digest_stable():
    limits = SkillIOLimits("io-policy", "1", 1024, 2048, 6, 32, 500)
    assert (
        limits.digest
        == SkillIOLimits(
            policy_id="io-policy",
            policy_revision="1",
            max_input_bytes=1024,
            max_output_bytes=2048,
            max_object_depth=6,
            max_properties=32,
            timeout_ms=500,
        ).digest
    )


def test_write_policies_and_arbitrary_executor_urls_fail_closed():
    for side_effect in (
        SideEffectClass.UNKNOWN,
        SideEffectClass.IDEMPOTENT_WRITE,
        SideEffectClass.NON_IDEMPOTENT_WRITE,
    ):
        with pytest.raises(SkillInvocationError, match="SKILL_SIDE_EFFECT_NOT_ALLOWED"):
            SideEffectPolicy("policy", "1", "a" * 64, side_effect)
    with pytest.raises(SkillInvocationError, match="EXECUTOR_ENDPOINT_NOT_ALLOWLISTED"):
        HttpReadOnlySkillExecutor(
            executor_id="executor",
            executor_revision="1",
            endpoint="https://example.invalid/invoke",
        )
