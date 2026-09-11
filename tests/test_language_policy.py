import os
import re
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Forbidden patterns per SN-082 (Language Policy) and SN-096 (Intoxication Claims)
# Formatted to prevent self-matching
FORBIDDEN_PATTERNS = [
    # Guilt / violation claims from AI alone
    re.compile(r"\bviolation\s+detected\b", re.IGNORECASE),
    re.compile(r"\bdriver\s+is\s+guilty\b", re.IGNORECASE),
    re.compile(r"\boffence\s+confirmed\b", re.IGNORECASE),
    re.compile(r"\bguilty\s+driver\b", re.IGNORECASE),
    re.compile(r"\bconfirmed\s+violation\s+by\s+ai\b", re.IGNORECASE),

    # Intoxication / Drunk driving detection claims (SN-096)
    re.compile(r"\bdrunk\s+detection\b", re.IGNORECASE),
    re.compile(r"\bintoxication\s+detect\b", re.IGNORECASE),
    re.compile(r"\balcohol.*camera\b", re.IGNORECASE),
    re.compile(r"\bdui\s+detect\b", re.IGNORECASE),
    re.compile(r"\bdriver\s+is\s+drunk\b", re.IGNORECASE),
    re.compile(r"\bdetect\s+drunk\b", re.IGNORECASE),
    re.compile(r"\bdetect\s+intoxication\b", re.IGNORECASE),
    re.compile(r"\bdrunken\s+driving\s+detected\b", re.IGNORECASE),
]

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".system_generated",
    ".gemini",
    "dist",
    "build",
    ".coverage",
    "graphify-out",
}

EXCLUDED_FILES = {
    "test_language_policy.py",
}

FILE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".md", ".json", ".yaml", ".yml"
}


def scan_file_for_violations(file_path: str):
    """Scans a file line by line for forbidden language policy phrases.
    For code/UI files: zero tolerance.
    For docs: allows explicit statements of prohibition (e.g. 'cannot detect intoxication',
    'does not detect', 'prohibited') or citations in policy tables.
    """
    violations = []
    is_doc = file_path.endswith(".md")
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                lower_line = line.lower()
                # Skip policy definitions, checklist test definitions, and explicitly stated prohibitions
                if is_doc:
                    if (
                        "forbidden" in lower_line
                        or "cannot" in lower_line
                        or "does not" in lower_line
                        or "we don't" in lower_line
                        or "prohibited" in lower_line
                        or "no visual" in lower_line
                        or "test_language_policy" in lower_line
                        or "sn-082" in lower_line
                        or "sn-096" in lower_line
                        or 'introducing "violation detected"' in lower_line
                        or "q&a" in lower_line
                        or "how do you" in lower_line
                        or "?" in line
                        or line.strip().startswith("|")
                    ):
                        continue

                for pat in FORBIDDEN_PATTERNS:
                    if pat.search(line):
                        violations.append((file_path, line_no, line.strip(), pat.pattern))
    except Exception:
        pass
    return violations



def test_repo_language_policy_compliance():
    """SN-082 & SN-096: Enforces language policy across the entire repository.
    AI may only flag suspicion ('UNVERIFIED', 'flagged for review');
    it must never claim guilt or confirmed violations, and cannot claim intoxication detection.
    """
    all_violations = []

    for root, dirs, files in os.walk(REPO_ROOT):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]

        for file in files:
            if file in EXCLUDED_FILES:
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext not in FILE_EXTENSIONS:
                continue

            full_path = os.path.join(root, file)
            violations = scan_file_for_violations(full_path)
            all_violations.extend(violations)

    if all_violations:
        msg_lines = [f"Language policy violations found ({len(all_violations)} total):"]
        for path, line_no, content, pat in all_violations:
            rel_path = os.path.relpath(path, REPO_ROOT)
            msg_lines.append(f"  {rel_path}:{line_no} -> pattern '{pat}' matched: '{content}'")
        pytest.fail("\n".join(msg_lines))


def test_language_policy_detects_mutation():
    """Mutation test: asserts that introducing 'Violation detected' or 'DUI detect'
    correctly triggers a violation.
    """
    sample_text_1 = "Camera CAM-01: Violation detected at 14:00"
    matches_1 = [pat.pattern for pat in FORBIDDEN_PATTERNS if pat.search(sample_text_1)]
    assert len(matches_1) > 0, "Mutation 'Violation detected' must be caught by policy!"

    sample_text_2 = "AI algorithm for DUI detect in traffic"
    matches_2 = [pat.pattern for pat in FORBIDDEN_PATTERNS if pat.search(sample_text_2)]
    assert len(matches_2) > 0, "Mutation 'DUI detect' must be caught by policy!"

    sample_text_clean = "Dangerous driving behaviour flagged for review. Status: UNVERIFIED."
    matches_clean = [pat.pattern for pat in FORBIDDEN_PATTERNS if pat.search(sample_text_clean)]
    assert len(matches_clean) == 0, "Permitted cautious phrasing must pass!"
