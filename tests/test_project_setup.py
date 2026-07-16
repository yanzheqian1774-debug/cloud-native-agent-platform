"""Tests for the repository engineering foundation."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_supported_python_version() -> None:
    """The project must run on Python 3.12."""
    assert sys.version_info[:2] == (3, 12)


def test_required_project_files_exist() -> None:
    """The repository must contain its essential engineering files."""
    required_files = [
        "README.md",
        "ROADMAP.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "Makefile",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".gitignore",
        ".env.example",
    ]

    missing_files = [
        relative_path
        for relative_path in required_files
        if not (PROJECT_ROOT / relative_path).is_file()
    ]

    assert not missing_files, f"Missing project files: {missing_files}"


def test_required_directories_exist() -> None:
    """The repository must contain its core component directories."""
    required_directories = [
        "docs",
        "adr",
        "architecture",
        "manifests",
        "operator",
        "runtime",
        "gateway",
        "workflow",
        "scripts",
        "tests",
    ]

    missing_directories = [
        relative_path
        for relative_path in required_directories
        if not (PROJECT_ROOT / relative_path).is_dir()
    ]

    assert not missing_directories, (
        f"Missing project directories: {missing_directories}"
    )
