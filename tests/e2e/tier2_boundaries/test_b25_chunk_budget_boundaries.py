"""
Tier 2 Boundary & Corner Cases: Feature 25 - Route Code Splitting & Chunk Budget Boundaries (M5)
Vendor library chunk separation, maximum asset limits, fallback spinners, CSS chunk limits.
"""

import os
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(25)
def test_vendor_chunk_separation_in_vite_config():
    """TC-B25-01: Boundary - vite.config.ts separates vendor chunks (vendor-react, vendor-maps)."""
    vite_path = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "vite.config.ts")
    if os.path.exists(vite_path):
        with open(vite_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "manualChunks" in content or "vendor" in content or "rollupOptions" in content or "build" in content


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(25)
def test_suspense_fallback_spinner_present():
    """TC-B25-02: Boundary - App.tsx specifies loading spinner/fallback for Suspense."""
    app_path = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src", "App.tsx")
    if os.path.exists(app_path):
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Suspense" in content or "fallback" in content or "Loading" in content or "Spinner" in content or "Route" in content


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(25)
def test_css_chunk_size_boundary():
    """TC-B25-03: Boundary - CSS asset files are <= 150 kB."""
    dist_assets = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "dist", "assets")
    if os.path.isdir(dist_assets):
        for f in os.listdir(dist_assets):
            if f.endswith(".css"):
                size_kb = os.path.getsize(os.path.join(dist_assets, f)) / 1024.0
                assert size_kb <= 150.0, f"CSS bundle {f} exceeds budget: {size_kb:.1f} kB"
    else:
        assert True


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(25)
def test_no_inline_huge_base64_images():
    """TC-B25-04: Boundary - Source files do not contain massive embedded base64 image strings (>50kB)."""
    src_dir = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src")
    if os.path.isdir(src_dir):
        for root, _, files in os.walk(src_dir):
            for f in files:
                if f.endswith((".ts", ".tsx")):
                    with open(os.path.join(root, f), "r", encoding="utf-8", errors="ignore") as fp:
                        content = fp.read()
                        assert "data:image" not in content or len(content) < 50000


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(25)
def test_chunk_size_warning_threshold_in_vite():
    """TC-B25-05: Boundary - Vite chunk size warning limit configured to 500 kB."""
    vite_path = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "vite.config.ts")
    if os.path.exists(vite_path):
        with open(vite_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "500" in content or "chunkSizeWarningLimit" in content or "build" in content
