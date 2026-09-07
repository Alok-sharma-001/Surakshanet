#!/usr/bin/env python3
"""
Unified E2E Test Suite Runner for Surakshanet ITS.
Supports 4-tier filtering, milestone-based progressive testability,
feature targeting, and output reporting.

Usage:
  python tests/e2e/run_e2e_tests.py [options]

Examples:
  python tests/e2e/run_e2e_tests.py --tier 1
  python tests/e2e/run_e2e_tests.py --tier 2
  python tests/e2e/run_e2e_tests.py --milestone m1
  python tests/e2e/run_e2e_tests.py --feature 1
  python tests/e2e/run_e2e_tests.py --all -v
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path


def is_running_in_docker() -> bool:
    """Check if the current process is running inside a container."""
    if os.path.exists("/.dockerenv"):
        return True
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read()
    except Exception:
        return False


def build_pytest_args(args: argparse.Namespace) -> list:
    """Construct pytest command arguments based on CLI flags."""
    pytest_args = []

    # Path selection
    if args.tier == "1":
        pytest_args.append("tests/e2e/tier1_features")
    elif args.tier == "2":
        pytest_args.append("tests/e2e/tier2_boundaries")
    elif args.tier == "3":
        pytest_args.append("tests/e2e/tier3_combinations")
    elif args.tier == "4":
        pytest_args.append("tests/e2e/tier4_scenarios")
    else:
        pytest_args.append("tests/e2e")

    # Milestone filtering
    if args.milestone and args.milestone.lower() != "all":
        pytest_args.extend(["-m", args.milestone.lower()])

    # Feature filtering
    if args.feature:
        feat_str = f"test_*f{int(args.feature):02d}*.py"
        pytest_args.extend(["-k", f"f{int(args.feature):02d} or b{int(args.feature):02d}"])

    if args.keyword:
        pytest_args.extend(["-k", args.keyword])

    if args.verbose:
        pytest_args.append("-v")

    if args.failfast:
        pytest_args.append("-x")

    if args.collect_only:
        pytest_args.append("--collect-only")

    if args.json_report:
        pytest_args.extend(["--json-report", f"--json-report-file={args.json_report}"])

    return pytest_args


def run_tests() -> int:
    parser = argparse.ArgumentParser(description="Surakshanet E2E Test Suite Runner")
    parser.add_argument("--tier", choices=["1", "2", "3", "4", "all"], default="all",
                        help="Select test tier to execute")
    parser.add_argument("--milestone", choices=["m1", "m2", "m3", "m4", "m5", "m6", "all"],
                        default=None, help="Filter by milestone marker")
    parser.add_argument("--feature", type=int, default=None,
                        help="Run tests covering a specific feature index (1..31)")
    parser.add_argument("-k", "--keyword", type=str, default=None,
                        help="Filter test functions by expression/keyword")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose pytest output")
    parser.add_argument("-x", "--failfast", action="store_true", help="Stop on first failure")
    parser.add_argument("--collect-only", action="store_true", help="Only collect and count tests")
    parser.add_argument("--json-report", type=str, default=None, help="Output JSON report path")
    parser.add_argument("--docker", action="store_true", help="Force execution via Docker container")
    parser.add_argument("--local", action="store_true", help="Force execution locally without Docker")

    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent.parent
    pytest_args = build_pytest_args(args)

    in_container = is_running_in_docker()
    use_docker = (not in_container and not args.local) or args.docker

    print("=" * 70)
    print("SURAKSHANET ITS - E2E TEST SUITE RUNNER")
    print(f"Target Tier:      {args.tier.upper()}")
    print(f"Target Milestone: {args.milestone.upper() if args.milestone else 'ALL'}")
    print(f"Target Feature:   {args.feature if args.feature else 'ALL'}")
    print(f"Execution Engine: {'Docker Container' if use_docker else 'Local Host'}")
    print("=" * 70)

    if use_docker:
        # Check if backend image and network are up
        cmd = [
            "docker", "run", "--rm",
            "--network", "infra_surakshanet-network",
            "-e", "PYTHONPATH=/workspace",
            "-v", f"{project_root}:/workspace",
            "-w", "/workspace",
            "surakshanet/surakshanet-backend:latest",
            "pytest"
        ] + pytest_args
    else:
        # Local execution using python / pytest
        pytest_bin = str(project_root / ".venv" / "bin" / "pytest")
        if not os.path.exists(pytest_bin):
            pytest_bin = "pytest"

        env = dict(os.environ)
        env["PYTHONPATH"] = str(project_root)
        cmd = [pytest_bin] + pytest_args

    print(f"Command: {' '.join(cmd)}\n")
    sys.stdout.flush()

    try:
        proc = subprocess.run(cmd, cwd=str(project_root))
        return proc.returncode
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user.")
        return 130
    except Exception as e:
        print(f"Execution failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
