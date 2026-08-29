# Supplier Quality Demo Scenario Pack v1

This directory is the sanitized, deterministic configuration input for the
bounded v0.2 supplier-quality Demo. It is not production data, a Runtime, a
permission grant, a role-publication mechanism, or live execution Evidence.

Fixed identity:

- scenario: `s5-v0.2-supplier-quality-v1`
- namespace: `s5-v02-supplier-quality-demo`
- tenant: `tenant-a`
- security domain: `supplier-quality`

## Provenance boundary

- `DEMO_CONFIGURATION` labels the configuration, cases, catalog declarations,
  namespace, and read-only Knowledge inputs.
- `SYNTHETIC_HISTORY` labels every historical example. Synthetic history is
  never an execution result or Evidence.
- `LIVE_EXECUTION` is declared as an empty, runtime-owned output class. This
  pack contains no live execution record and cannot fabricate one.

## Verify and bootstrap

The scripts require every target explicitly. Use an absolute target path whose
final component is the exact namespace:

```sh
./examples/s5-v0.2-supplier-quality/bootstrap.sh \
  --scenario s5-v0.2-supplier-quality-v1 \
  --namespace s5-v02-supplier-quality-demo \
  --target-dir /tmp/s5-v02-supplier-quality-demo
```

Bootstrap validates all repository inputs against `checksums.sha256`, creates
only the exact target, and writes a scope marker. Running it again produces the
same file tree and contents. It does not contact Kubernetes, provision a
Runtime, create credentials, grant permissions, publish roles, ingest
Knowledge, or invoke a Provider.

## Bounded reset

Reset refuses missing arguments, relative paths, `/`, wildcard-like values,
namespace/path mismatches, foreign scope markers, and missing confirmation:

```sh
./examples/s5-v0.2-supplier-quality/reset.sh \
  --scenario s5-v0.2-supplier-quality-v1 \
  --namespace s5-v02-supplier-quality-demo \
  --target-dir /tmp/s5-v02-supplier-quality-demo \
  --confirm s5-v0.2-supplier-quality-v1@s5-v02-supplier-quality-demo
```

Reset deletes only the exact marked target. Repeating reset after successful
removal is a no-op. No default Kubernetes context or namespace is used.

## Supported boundary

The materialized files are exact Package 8 scenario input only. Clean
reproduction means checksum verification and deterministic local
materialization; it does not claim Golden Demo acceptance, production
Knowledge ingestion, production authority, certification, or release
readiness.
