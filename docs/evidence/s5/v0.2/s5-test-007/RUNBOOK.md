# Package 8 Reproduction Runbook

All caches and generated dependencies must remain outside the repository.

```sh
export UV_CACHE_DIR=/private/tmp/s5-test-007-uv-cache
export UV_PROJECT_ENVIRONMENT=/private/tmp/s5-test-007-venv
uv run pytest -q tests/test_s5_test_007_enhanced_golden_demo_acceptance.py
uv run pytest -q tests/test_s5_impl_036_supplier_quality_scenario_pack.py \
  tests/test_s5_impl_037_package_7_live_integration.py \
  console/backend/tests/test_supplier_quality_demo.py \
  console/backend/tests/test_supplier_quality_demo_api.py
uv run ruff check .
uv run ruff format --check .
make check
git diff --check
```

For Browser QA, materialize Package 7 into an absolute temporary target, start
the backend with that target, and run an external frontend validation copy with
`VITE_SUPPLIER_QUALITY_DEMO_MODE=live`. Exercise the backend-issued journey; do
not seed the coordinator or use a fixture as live. Test Product and Technical
views in English and zh-CN at `1280×720` and `390×844`.

Rollback rehearsal is exact-scope removal of the nine Package 8 paths. It does
not rewrite canonical revisions, Outcomes, Evidence or Package 7 history.
