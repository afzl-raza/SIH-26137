import sys
import os
import re
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# backend/tests -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "requirements_traceability.md"

PATH_PREFIXES = ("backend/", "frontend/", "docs/", "experiments/")


def _extract_candidate_paths(text: str):
    """Pulls file-path-looking backtick spans out of the traceability table,
    skipping API routes (e.g. `POST /api/...`) and glob/placeholder patterns
    (e.g. `experiments/<name>/*.csv`)."""
    candidates = []
    for token in re.findall(r"`([^`]+)`", text):
        if not token.startswith(PATH_PREFIXES):
            continue
        if any(ch in token for ch in "<>{}*"):
            continue
        # Strip a trailing ::symbol reference, keep just the file path.
        path_part = token.split("::")[0].strip()
        candidates.append(path_part)
    return candidates


def test_traceability_paths_exist():
    """Guards docs/requirements_traceability.md against silently rotting the
    way Documnetation.md did (see Documnetation.md's own correction notes) -
    every referenced module path must actually exist on disk."""
    text = DOC_PATH.read_text(encoding="utf-8")
    candidates = _extract_candidate_paths(text)

    assert len(candidates) > 5, "expected several file-path references in the traceability table"

    missing = [p for p in candidates if not (REPO_ROOT / p).exists()]
    assert missing == [], f"requirements_traceability.md references paths that no longer exist: {missing}"
