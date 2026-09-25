"""Build plans per artifact type (MOCK of the organization's build logic).

A plan is the ordered list of commands the real build action would run for an
artifact type. Adding an artifact type means adding one entry to BUILD_PLANS,
mirroring VALIDATORS in prcheck-utils-action.
"""

from __future__ import annotations

from typing import Dict, List

BUILD_PLANS: Dict[str, List[str]] = {
    "backend": [
        "mvn -B -ntp verify",
        "publish target/*.jar to the artifact repository",
    ],
    "frontend": [
        "npm ci",
        "npm run build",
        "publish dist/ to the artifact repository",
    ],
}


class UnsupportedArtifactType(ValueError):
    pass


def resolve_plan(artifact_type: str) -> List[str]:
    key = (artifact_type or "").strip().lower()
    if key not in BUILD_PLANS:
        supported = ", ".join(sorted(BUILD_PLANS))
        raise UnsupportedArtifactType(
            f"Unsupported artifact_type '{artifact_type}'. Supported values: {supported}."
        )
    return list(BUILD_PLANS[key])
