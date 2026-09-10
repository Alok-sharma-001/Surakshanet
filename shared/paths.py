import os
from typing import Iterable, Optional


def find_existing(candidates: Iterable[str]) -> Optional[str]:
    """Return the first path in `candidates` that exists, or None."""
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def resolve_repo_path(*parts: str) -> Optional[str]:
    """Resolve a path under the repo root, trying the container layout
    (/app/<parts>), a host checkout (repo-root-relative), and CWD-relative,
    in that order."""
    rel = os.path.join(*parts)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        rel,
        os.path.join(os.getcwd(), rel),
        os.path.join(repo_root, rel),
        os.path.join("/app", rel),
    ]
    return find_existing(candidates)
