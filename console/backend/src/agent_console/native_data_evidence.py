"""Independent, read-only measurement view over an authorized Native artifact."""

from agent_runtime.native_loop import digest, snapshot

from .native_data_skill import exact_executor
from .resource_use_domain import canonical_digest


def verified_report(output, revision, source, reference):
    """No producing Skill invocation/model; invalid evidence stays unmeasurable.

    Callers must first obtain the artifact through the original current authority,
    immutable artifact digest and successful resource-use lineage. This function
    does not authorize that read and does not accept arbitrary model self-reports.
    """
    try:
        adapter = exact_executor(revision).adapter
        adapter.validate(source)
        if (
            not isinstance(output, dict)
            or output.get("schemaVersion") != "native-data-output.v1"
            or output.get("operation") != "RENDER_REPORT"
            or output.get("synthetic") is not True
            or output.get("externalWrites") is not False
            or output.get("businessConclusion") != "UNDETERMINED"
            or output.get("adapter") != adapter.descriptor()
            or output.get("source") != source
            or output.get("sourceSnapshot") != reference
            or output.get("sourceDigest") != canonical_digest(source)
        ):
            return None
        loop = output.get("nativeLoop")
        if not isinstance(loop, dict) or loop.get("status") != "SUCCEEDED":
            return None
        trace = loop.get("trace")
        if (
            not isinstance(trace, list)
            or not trace
            or not all(isinstance(s, dict) for s in trace)
        ):
            return None
        if (
            trace[-1].get("decision", {}).get("action") != "FINISH"
            or trace[-1].get("verification", {}).get("passed") is not True
        ):
            return None
        observations = [
            s["observation"] for s in trace if isinstance(s.get("observation"), dict)
        ]
        library = adapter.tools(source, reference)
        expected = library.invoke("build_report", {})
        reports = [
            o.get("output")
            for o in observations
            if o.get("kind") == "TOOL_RESULT" and o.get("tool") == "build_report"
        ]
        if (
            not reports
            or reports[-1] != expected
            or output.get("nativeReport") != expected
        ):
            return None
        if not library.verify({"observations": observations}, loop.get("answer"))[
            "passed"
        ]:
            return None
        receipt = {
            "schemaVersion": "native-data-report-verification.v1",
            "adapterDigest": adapter.configuration_digest,
            "sourceSnapshot": reference,
            "sourceDigest": canonical_digest(source),
            "reportDigest": expected["reportDigest"],
            "businessAcceptance": False,
        }
        if output.get("nativeReportVerification") != {
            **receipt,
            "digest": digest(receipt),
        }:
            return None
        return snapshot(expected)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None
