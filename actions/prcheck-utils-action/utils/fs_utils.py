"""Filesystem helpers shared by the validators."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List

# Directories that never contain source the PR author intends to ship.
# Kept deliberately small: anything more opinionated belongs in configuration.
SKIPPED_DIRS = frozenset({".git"})


class PathConfigError(ValueError):
    """Raised for a configured path that is unsafe or unusable."""


def resolve_within(root: Path, relative: str, label: str) -> Path:
    """Resolve ``relative`` against ``root`` and refuse anything that escapes it.

    Configured paths come from workflow inputs, so they are treated as untrusted:
    absolute paths and ``..`` traversal outside the repository are rejected.
    """
    root = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise PathConfigError(
            f"{label} '{relative}' resolves outside the repository root; "
            "use a path relative to the repository root"
        ) from None
    return candidate


def find_files(base: Path, predicate: Callable[[str], bool]) -> List[Path]:
    """Recursively find files under ``base`` whose filename satisfies ``predicate``.

    Results are sorted so diagnostics are deterministic. Symlinked directories
    are not followed.
    """
    matches: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIPPED_DIRS)
        for name in filenames:
            if predicate(name):
                matches.append(Path(dirpath) / name)
    return sorted(matches)


def display_path(path: Path, root: Path) -> str:
    """Repository-relative POSIX path for messages and annotations."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
