"""Explicit opt-in configuration; this config supplies no resource authority."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class SalesSupplementFeatures:
    sales_v2: bool = False
    supplement: bool = False

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]):
        def flag(name):
            value = environment.get(name, "false")
            if value not in {"true", "false"}:
                raise ValueError("SALES_SUPPLEMENT_CONFIGURATION_INVALID")
            return value == "true"

        result = cls(
            flag("SALES_GROSS_PROFIT_V2_CANDIDATE"),
            flag("SALES_SUPPLEMENT_CANDIDATE"),
        )
        if result.supplement and not result.sales_v2:
            raise ValueError("SALES_SUPPLEMENT_V2_REQUIRED")
        return result
