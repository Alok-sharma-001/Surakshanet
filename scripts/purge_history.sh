#!/usr/bin/env bash
# ==============================================================================
# SurakshaNet Secret Remediation: History Purge Script
# Purges committed secret key 'surakshanet-key.pem' from all Git history.
# ==============================================================================

set -euo pipefail

TARGET_FILE="surakshanet-key.pem"

echo "=== SurakshaNet History Purge Utility ==="
echo "Target secret file to purge: ${TARGET_FILE}"

# Check git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: Current directory is not a Git repository." >&2
    exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

# Confirm with user unless --force / -y is passed
AUTO_CONFIRM=false
for arg in "$@"; do
    if [[ "$arg" == "--force" || "$arg" == "-y" || "$arg" == "-f" ]]; then
        AUTO_CONFIRM=true
    fi
done

if [[ "${AUTO_CONFIRM}" != "true" ]]; then
    echo ""
    echo "WARNING: This operation will rewrite Git commit history across all branches."
    echo "Existing commit hashes will change. Ensure your team has backed up any unpushed work."
    read -rp "Do you want to proceed with rewriting git history? (y/N): " CONFIRM
    if [[ "${CONFIRM}" != "y" && "${CONFIRM}" != "Y" ]]; then
        echo "Operation cancelled by user."
        exit 0
    fi
fi

echo "[1/4] Checking history rewrite tooling..."

if command -v git-filter-repo >/dev/null 2>&1; then
    echo "[2/4] Executing history purge via git-filter-repo..."
    git-filter-repo --invert-paths --path "${TARGET_FILE}" --force
else
    echo "[2/4] git-filter-repo not found. Executing history purge via git filter-branch..."
    export FILTER_BRANCH_SQUELCH_WARNING=1
    git filter-branch --force \
        --index-filter "git rm --cached --ignore-unmatch ${TARGET_FILE}" \
        --prune-empty \
        --tag-name-filter cat -- --all
fi

echo "[3/4] Purging original refs and expiring reflog..."
rm -rf .git/refs/original/
git reflog expire --expire=now --all

echo "[4/4] Aggressive garbage collection..."
git gc --prune=now --aggressive

echo ""
echo "=== History Purge Completed Successfully ==="
echo "The file '${TARGET_FILE}' has been removed from all historical commits."
echo "Verify with: git log --all --full-history -- '${TARGET_FILE}' (should be empty)"
