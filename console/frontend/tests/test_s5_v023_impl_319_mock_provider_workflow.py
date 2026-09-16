from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[3]


def test_dedicated_workflow_builds_both_required_vite_modes() -> None:
    workflow = (
        REPOSITORY_ROOT / ".github" / "workflows" / "s5-v023-impl-319-mock-provider.yml"
    ).read_text()
    assert "VITE_SUPPLIER_QUALITY_DEMO_MODE: live" in workflow
    assert "VITE_PROBLEM_DRAFT_ASSISTANCE: enabled" in workflow
    assert "bash scripts/acceptance/s5_v023_impl_319_mock_provider.sh" in workflow


def test_dedicated_playwright_collection_and_cleanup_are_fail_closed() -> None:
    config = (
        REPOSITORY_ROOT / "console" / "frontend" / "playwright.s5-319.config.ts"
    ).read_text()
    runner = (
        REPOSITORY_ROOT / "scripts" / "acceptance" / "s5_v023_impl_319_mock_provider.sh"
    ).read_text()
    cleanup = (
        REPOSITORY_ROOT / "scripts" / "acceptance" / "s5_v023_impl_319_owned_cleanup.sh"
    ).read_text()
    assert 'testMatch: "s5-319-draft-assistance.real.spec.ts"' in config
    assert 'for marker in ("新建对话", "AI 问题理解与草稿辅助")' in runner
    assert "browser_status=$?" in runner
    assert 'exit "$browser_status"' in runner
    assert "local exit_code=$?" in cleanup
    assert "local status" not in cleanup
