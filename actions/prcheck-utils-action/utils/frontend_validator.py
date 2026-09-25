"""Frontend artifact consistency: every XML file under a configured path must be well-formed.

Only well-formedness is checked (the document parses). Contents are not
compared and no schema validation is performed.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

from .fs_utils import PathConfigError, display_path, find_files, resolve_within
from .result_utils import CheckResult

XML_SUFFIX = ".xml"


def check_well_formed(xml_file: Path) -> str | None:
    """Return None if the file parses, else a human-readable parse error."""
    try:
        ET.parse(xml_file)
    except ET.ParseError as exc:
        return str(exc)
    return None


def validate_frontend(root: Path, config: Dict[str, str]) -> CheckResult:
    """Recursively validate XML files below ``config['xml_path']`` (relative to ``root``)."""
    xml_path = (config.get("xml_path") or "").strip()
    if not xml_path:
        return CheckResult.failure(
            "xml_path is required when artifact_type is 'frontend'; "
            "pass the directory containing the XML files (relative to the repository root)."
        )

    try:
        base = resolve_within(root, xml_path, "xml_path")
    except PathConfigError as exc:
        return CheckResult.failure(str(exc), xml_path=xml_path)

    if not base.exists():
        return CheckResult.failure(f"Configured xml_path '{xml_path}' does not exist in the repository.", xml_path=xml_path)
    if not base.is_dir():
        return CheckResult.failure(f"Configured xml_path '{xml_path}' is not a directory.", xml_path=xml_path)

    xml_files = find_files(base, lambda name: name.lower().endswith(XML_SUFFIX))
    if not xml_files:
        return CheckResult.failure(
            f"No {XML_SUFFIX} files found under xml_path '{xml_path}'.",
            xml_path=xml_path,
            files_inspected=[],
        )

    valid: List[str] = []
    invalid: List[Dict[str, str]] = []
    for xml_file in xml_files:
        rel = display_path(xml_file, root)
        error = check_well_formed(xml_file)
        if error is None:
            valid.append(rel)
        else:
            invalid.append({"file": rel, "error": error})

    details = {
        "xml_path": xml_path,
        "files_inspected": [display_path(f, root) for f in xml_files],
        "valid_files": valid,
        "invalid_files": invalid,
    }

    if invalid:
        return CheckResult(
            passed=False,
            summary=f"{len(invalid)} of {len(xml_files)} XML file(s) under '{xml_path}' are not well-formed.",
            errors=[f"{item['file']}: {item['error']}" for item in invalid],
            details=details,
        )

    return CheckResult(
        passed=True,
        summary=f"All {len(xml_files)} XML file(s) under '{xml_path}' are well-formed.",
        details=details,
    )
