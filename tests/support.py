"""Test helpers: make the action's modules importable and locate fixtures."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTION_DIR = REPO_ROOT / "actions" / "prcheck-utils-action"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

if str(ACTION_DIR) not in sys.path:
    sys.path.insert(0, str(ACTION_DIR))
