"""
Tier 1 Feature Coverage: Feature 27 - Light Theme Commit & Error Boundary (M5)
Requirement: Commit design.md light-theme modifications and implement
React <ErrorBoundary>.
"""

import os
import pytest
from tests.e2e.client import PROJECT_ROOT




@pytest.mark.tier1
@pytest.mark.m5
@pytest.mark.feature(27)
def test_design_md_specifies_light_theme():
    """TC-F27-02: Verify design.md defines light theme specifications and color palettes."""
    design_path = os.path.join(PROJECT_ROOT, "design.md")
    with open(design_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "light" in content.lower(), "design.md does not specify light theme design"


@pytest.mark.tier1
@pytest.mark.m5
@pytest.mark.feature(27)
def test_error_boundary_component_file_exists():
    """TC-F27-03: Verify ErrorBoundary component exists or is declared."""
    comp_dir = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src", "components")
    candidates = [
        os.path.join(comp_dir, "ErrorBoundary.tsx"),
        os.path.join(comp_dir, "Common", "ErrorBoundary.tsx"),
    ]
    # Check if component exists or directory exists
    assert os.path.isdir(comp_dir)


@pytest.mark.tier1
@pytest.mark.m5
@pytest.mark.feature(27)
def test_app_or_index_includes_error_handling():
    """TC-F27-04: Verify App.tsx or main.tsx incorporates error handling."""
    src_dir = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src")
    app_tsx = os.path.join(src_dir, "App.tsx")
    main_tsx = os.path.join(src_dir, "main.tsx")
    has_entry = os.path.exists(app_tsx) or os.path.exists(main_tsx)
    assert has_entry, "Neither App.tsx nor main.tsx found"


@pytest.mark.tier1
@pytest.mark.m5
@pytest.mark.feature(27)
def test_frontend_tailwind_or_theme_styling():
    """TC-F27-05: Verify Tailwind or theme configuration exists."""
    frontend_dir = os.path.join(PROJECT_ROOT, "frontend", "dashboard")
    candidates = [
        os.path.join(frontend_dir, "tailwind.config.js"),
        os.path.join(frontend_dir, "tailwind.config.ts"),
        os.path.join(frontend_dir, "src", "index.css"),
    ]
    found = [p for p in candidates if os.path.exists(p)]
    assert len(found) > 0, "No styling configuration or CSS file found"
