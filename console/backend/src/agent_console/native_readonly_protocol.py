"""Internal v4 projections retain explicit adapter identity across original owners."""

from typing import Literal

from .cost_execution_revision import CostExecutionRevisionRequest
from .owned_business_native_policy import NativeAdapterBinding
from .readonly_continuation_policy import ReadonlyWork


class NativeReadonlyWork(ReadonlyWork):
    case: Literal["native_readonly"]
    adapter: NativeAdapterBinding


class NativeExecutionRevisionRequest(CostExecutionRevisionRequest):
    case: Literal["native_readonly"]
    adapter: NativeAdapterBinding


def scope_adapter(work):
    scope = getattr(work, "businessScope", None)
    if scope is None or scope.case != "native_readonly":
        return None
    return scope.adapter
