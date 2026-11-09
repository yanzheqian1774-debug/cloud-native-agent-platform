# ruff: noqa: RUF001 -- Business resource descriptions.
"""Distinct v2 draft bundle; model execution needs explicit Native composition."""

from .native_loop_skill import (
    VALIDATED_CONFIGURATION as CONFIGURATION,
)
from .native_loop_skill import (
    NativeValidatedLoopSkillExecutor,
)
from .tabular_resource_bundle import resource_content as tabular_content


def resource_content(source):
    bundle = tabular_content(source)
    revision = NativeValidatedLoopSkillExecutor.revision
    skill = bundle["skill"]
    skill["description"] = (
        "真实模型根据只读工具结果决定下一步，核对异常原始行并独立复算。"
    )
    skill["instructions"] = (
        "先读取资料，执行分析，再返回报告。分析任务内部按实际观察选择工具，不预设固定调查路径。"
    )
    skill["capabilities"] = CONFIGURATION["operations"]
    skill["operations"] = [
        op for op in skill["operations"] if op["name"] in CONFIGURATION["operations"]
    ]
    for op in skill["operations"]:
        op.update(
            executorRevision=revision.executor_revision,
            executorConfigurationDigest=revision.configuration_digest,
        )
        op["ioLimits"].update(timeoutMs=480000, maxObjectDepth=24, maxProperties=20000)
    bundle["agent"].update(
        title="应用运行指标核查助手",
        businessPurpose="根据实际检查结果继续核对，返回可复算的指标异常报告。",
    )
    return bundle
