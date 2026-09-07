from pathlib import Path

ROOT = Path(__file__).parents[3]
FRONTEND = ROOT / "console" / "frontend" / "src"


def source(path: str) -> str:
    return (FRONTEND / path).read_text()


def test_wave_2_has_nine_routes_and_shared_navigation() -> None:
    app = source("App.tsx")
    shell = source("components/ConsoleShell.tsx")
    routes = (
        "/applications",
        "/agent-center",
        "/permissions",
        "/security",
        "/operations",
        "/models",
        "/usage",
        "/settings",
        "/help",
    )
    for route in routes:
        assert route in app
        assert route in shell
    assert "平台支撑导航" in shell


def test_wave_2_truthfulness_and_boundaries_are_explicit() -> None:
    pages = source("administration/PlatformSupportPages.tsx")
    for status in (
        "REAL",
        "PROTOTYPE_ONLY",
        "NOT_CONNECTED",
        "UNAVAILABLE",
        "PLANNED",
    ):
        assert status in pages
    for measurement in (
        "MEASURED",
        "NOT_COLLECTED",
        "NOT_MEASURABLE",
        "ESTIMATED",
        "STALE",
        "CONFLICTED",
    ):
        assert measurement in pages
    assert "不显示 0" in pages
    assert "不展示 secret 值" in pages
    assert "不等同数字员工、Agent Instance、Runtime Instance 或 Application" in pages
    assert "不替代各自工作台" in pages


def test_wave_2_uses_only_existing_catalog_truth() -> None:
    pages = source("administration/PlatformSupportPages.tsx")
    assert 'listProductResources("",agent?"AGENT":"","")' in pages
    assert "product catalog read-model" in pages
    assert "当前 frontend 没有申请、批准或拒绝 authority" in pages
    assert "没有安装 authority" in pages
    assert "没有模型目录、测量、价格或可用性权威" in pages


def test_wave_2_responsive_and_accessible_foundations() -> None:
    pages = source("administration/PlatformSupportPages.tsx")
    styles = source("styles/product-experience.css")
    assert 'role="tablist"' in pages
    assert 'role="tab"' in pages
    assert 'role="status"' in pages
    assert 'role="alert"' in pages
    assert ".px-support-grid,.px-support-links{grid-template-columns:1fr}" in styles
    assert ".px-shell :focus-visible" in styles
