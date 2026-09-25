"""Backend artifact consistency: every pom.xml must declare the same artifactId.

Only the project's own coordinate is compared, i.e. the ``<artifactId>`` that is
a direct child of the root ``<project>`` element. ``artifactId`` elements nested
in ``<parent>``, ``<dependencies>``, ``<plugins>`` etc. are unrelated and ignored.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

from .fs_utils import display_path, find_files
from .result_utils import CheckResult

POM_FILENAME = "pom.xml"


def _local_name(tag: str) -> str:
    """Strip an XML namespace: '{http://maven.apache.org/POM/4.0.0}project' -> 'project'."""
    return tag.rsplit("}", 1)[-1]


def extract_artifact_id(pom_path: Path) -> str:
    """Return the project artifactId of a POM, raising ValueError with a clear reason."""
    try:
        root = ET.parse(pom_path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"malformed XML: {exc}") from exc

    if _local_name(root.tag) != "project":
        raise ValueError(f"not a Maven POM (root element is <{_local_name(root.tag)}>, expected <project>)")

    for child in root:
        if isinstance(child.tag, str) and _local_name(child.tag) == "artifactId":
            value = (child.text or "").strip()
            if not value:
                raise ValueError("<artifactId> is present but empty")
            return value

    raise ValueError("no project-level <artifactId> element (a direct child of <project>)")


def validate_backend(root: Path, config: Dict[str, str]) -> CheckResult:
    """Recursively scan ``root`` for pom.xml files and require a single shared artifactId."""
    poms = find_files(root, lambda name: name == POM_FILENAME)
    if not poms:
        return CheckResult.failure(
            f"No {POM_FILENAME} files found in the repository; a backend artifact must contain at least one.",
            files_inspected=[],
        )

    artifact_ids: Dict[str, str] = {}
    errors: List[str] = []
    for pom in poms:
        rel = display_path(pom, root)
        try:
            artifact_ids[rel] = extract_artifact_id(pom)
        except ValueError as exc:
            errors.append(f"{rel}: {exc}")

    files_inspected = [display_path(p, root) for p in poms]
    groups: Dict[str, List[str]] = {}
    for rel, artifact_id in artifact_ids.items():
        groups.setdefault(artifact_id, []).append(rel)

    if len(groups) > 1:
        breakdown = "; ".join(f"'{aid}' in {', '.join(files)}" for aid, files in sorted(groups.items()))
        errors.append(f"artifactId mismatch: {len(groups)} distinct values found: {breakdown}")

    details = {
        "files_inspected": files_inspected,
        "artifact_ids": artifact_ids,
        "distinct_artifact_ids": sorted(groups),
        "files_by_artifact_id": {aid: files for aid, files in sorted(groups.items())},
    }

    if errors:
        return CheckResult(
            passed=False,
            summary=f"Backend artifact consistency FAILED for {len(poms)} {POM_FILENAME} file(s).",
            errors=errors,
            details=details,
        )

    (only_id,) = groups
    return CheckResult(
        passed=True,
        summary=f"All {len(poms)} {POM_FILENAME} file(s) declare artifactId '{only_id}'.",
        details=details,
    )
