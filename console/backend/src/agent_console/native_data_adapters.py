"""Explicit local Native data capabilities; descriptors never grant execution."""

from dataclasses import dataclass

from .native_delivery_tools import CONFIGURATION_DIGEST as DELIVERY_DIGEST
from .native_delivery_tools import NativeDeliveryTools
from .native_diagnostic_tools import NativeDiagnosticTools
from .resource_use_domain import canonical_digest
from .tabular_diagnostic_skill import CONFIGURATION as TABULAR_COMPUTATION
from .tabular_diagnostic_skill import validate_source as validate_tabular

OPERATIONS = ("READ_DATA", "VALIDATE_DATA", "ANALYZE_DATA", "RENDER_REPORT")


@dataclass(frozen=True)
class NativeDataAdapter:
    adapter_id: str
    revision: str
    configuration_digest: str
    source_schema: str
    operations: tuple[str, ...]
    library_type: type

    def descriptor(self):
        return {
            "adapterId": self.adapter_id,
            "adapterRevision": self.revision,
            "configurationDigest": self.configuration_digest,
            "sourceSchema": self.source_schema,
            "operations": list(self.operations),
            "effectPolicy": "READ_ONLY",
            "externalWrites": False,
        }

    def validate(self, source):
        if (
            not isinstance(source, dict)
            or source.get("schemaVersion") != self.source_schema
        ):
            raise ValueError("NATIVE_DATA_SOURCE_SCHEMA_MISMATCH")
        if self.library_type is NativeDiagnosticTools:
            validate_tabular(source)
        else:
            from .synthetic_delivery_skill import analyze

            analyze(source)

    def tools(self, source, reference):
        self.validate(source)
        library = self.library_type(source, reference)
        if self.library_type is NativeDiagnosticTools:
            library.answer_schema = {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "reportDigest": {"type": "string"},
                    "exceptionIds": {"type": "array", "items": {"type": "string"}},
                    "invalidIds": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["reportDigest", "exceptionIds", "invalidIds"],
            }
        return library


ADAPTERS = (
    NativeDataAdapter(
        "native-declarative-tabular-readonly",
        "1",
        canonical_digest(
            {
                "schemaVersion": "native-data-adapter.v1",
                "implementation": "native-diagnostic-operations.v1",
                "computation": TABULAR_COMPUTATION,
                "verifier": "tabular_evaluation.checks",
                "operations": OPERATIONS,
                "effectPolicy": "READ_ONLY",
            }
        ),
        "tabular-diagnostic-source.v1",
        OPERATIONS,
        NativeDiagnosticTools,
    ),
    NativeDataAdapter(
        "native-synthetic-delivery-readonly",
        "1",
        DELIVERY_DIGEST,
        "synthetic-delivery-source.v1",
        OPERATIONS,
        NativeDeliveryTools,
    ),
)


def resolve(descriptor):
    """Exact complete descriptor, no implicit latest or schema-only authorization."""
    matches = [adapter for adapter in ADAPTERS if adapter.descriptor() == descriptor]
    if len(matches) != 1:
        raise ValueError("NATIVE_DATA_ADAPTER_NOT_REGISTERED")
    return matches[0]


def capabilities(source_schema):
    """Read-only inventory; callers must separately validate sources and authority."""
    return [
        adapter.descriptor()
        for adapter in ADAPTERS
        if adapter.source_schema == source_schema
    ]


def configured(value):
    """Optional exact runtime capability list; absent means legacy only."""
    raw = value.get("nativeDataAdapters")
    if raw is None:
        return ()
    if not isinstance(raw, list) or not 1 <= len(raw) <= len(ADAPTERS):
        raise ValueError("NATIVE_DATA_RUNTIME_CONFIGURATION_INVALID")
    adapters = tuple(resolve(item) for item in raw)
    if len(set(adapters)) != len(adapters):
        raise ValueError("NATIVE_DATA_RUNTIME_CONFIGURATION_INVALID")
    return adapters
