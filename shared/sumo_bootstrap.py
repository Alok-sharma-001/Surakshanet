import os
import sys


def ensure_sumo_on_path(extra_paths: list[str] | None = None) -> None:
    """Put SUMO's tools/ dir and common dist-packages locations on sys.path."""
    candidate_paths = [
        os.path.join(os.environ.get("SUMO_HOME", "/usr/share/sumo"), "tools"),
        "/usr/share/sumo/tools",
        "/usr/lib/python3/dist-packages",
        "/usr/local/share/sumo/tools",
    ]
    if extra_paths:
        candidate_paths.extend(extra_paths)
    for p in candidate_paths:
        if os.path.exists(p) and p not in sys.path:
            sys.path.insert(0, p)
    if "SUMO_HOME" not in os.environ and os.path.exists("/usr/share/sumo"):
        os.environ["SUMO_HOME"] = "/usr/share/sumo"


def require_traci(extra_paths: list[str] | None = None):
    """Import traci or hard-exit with a diagnostic. For process entrypoints
    only (main.py, sumo_live_bridge.py, control_service/main.py) — SN-016's
    three named files. Not for library modules; see sumo_env.py, which
    catches its own ImportError instead (SN-005's graceful-degradation
    contract depends on that)."""
    ensure_sumo_on_path(extra_paths)
    try:
        import traci
        return traci
    except ImportError as exc:
        raise SystemExit(
            "FATAL: 'traci' is not importable from this interpreter.\n"
            f"  interpreter: {sys.executable}\n"
            "  fix: see docs/04-environment-setup.md §2 (SN-013)"
        ) from exc
