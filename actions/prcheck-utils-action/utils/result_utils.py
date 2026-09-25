"""Shared result structures for prcheck-utils-action.

Every PR check (existing or future) reports a ``CheckResult``. Results are
accumulated into a single ``result_map`` keyed by check name, and
``block_merge`` is derived from the whole map, not from any single check.

result_map shape (one entry per check)::

    {
      "<check_name>": {
        "passed":   bool,         # required; anything other than True counts as failed
        "required": bool,         # optional, default True; non-required checks never block
        "summary":  str,
        "errors":   [str, ...],
        "details":  {...},        # check-specific diagnostics
        ...                       # check-specific metadata (e.g. artifact_type)
      }
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


class ResultMapError(ValueError):
    """Raised when an incoming result_map cannot be interpreted safely."""


@dataclass
class CheckResult:
    passed: bool
    summary: str
    errors: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    required: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def failure(cls, summary: str, errors: List[str] | None = None, **details: Any) -> "CheckResult":
        return cls(passed=False, summary=summary, errors=list(errors or [summary]), details=dict(details))

    def to_dict(self) -> Dict[str, Any]:
        entry: Dict[str, Any] = {"passed": self.passed, "required": self.required}
        entry.update(self.metadata)
        entry["summary"] = self.summary
        entry["errors"] = list(self.errors)
        entry["details"] = dict(self.details)
        return entry


def parse_result_map(raw: str | None) -> Dict[str, Any]:
    """Parse a result_map produced by earlier checks. Empty input means no prior checks."""
    if raw is None or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResultMapError(f"Incoming result_map is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ResultMapError(
            f"Incoming result_map must be a JSON object keyed by check name, got {type(value).__name__}"
        )
    return value


def update_result_map(result_map: Dict[str, Any], check_name: str, result: CheckResult) -> Dict[str, Any]:
    """Return a copy of result_map with check_name set to result (replacing any previous entry)."""
    updated = dict(result_map)
    updated[check_name] = result.to_dict()
    return updated


def compute_block_merge(result_map: Dict[str, Any]) -> bool:
    """block_merge is true if any required check did not explicitly pass.

    Fail-safe rules: a malformed entry, a missing ``passed`` flag or a non-boolean
    ``passed`` value all count as failures. An empty map never unblocks merging
    by accident: with nothing checked there is nothing to vouch for the PR.
    """
    if not result_map:
        return True
    for entry in result_map.values():
        if not isinstance(entry, dict):
            return True
        if entry.get("required", True) is False:
            continue
        if entry.get("passed") is not True:
            return True
    return False


def failed_checks(result_map: Dict[str, Any]) -> List[str]:
    """Names of required checks that did not pass (for reporting)."""
    names = []
    for name, entry in result_map.items():
        if not isinstance(entry, dict):
            names.append(name)
        elif entry.get("required", True) is not False and entry.get("passed") is not True:
            names.append(name)
    return names
