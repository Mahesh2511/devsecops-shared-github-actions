#!/usr/bin/env python3
"""build-action entry point (MOCK of the organization's shared build action).

Selects the build plan for the explicit artifact_type and reports it. The real
toolchain commands are private, so the plan is printed instead of executed.
This action runs only after the PR check has passed; build.yml enforces that.

Inputs (environment variables set by action.yml, or CLI flags for local runs):
  BUILD_ARTIFACT_TYPE   backend | frontend   (--artifact-type)
  GITHUB_WORKSPACE      checked-out source   (--workspace)

Outputs ($GITHUB_OUTPUT):
  artifact_type   normalized artifact type that was built
  build_status    "mocked"
"""

from __future__ import annotations

import argparse
import os
import sys

from utils.build_plans import UnsupportedArtifactType, resolve_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mock organization build for an artifact type.")
    parser.add_argument("--artifact-type", default=os.environ.get("BUILD_ARTIFACT_TYPE", ""))
    parser.add_argument("--workspace", default=os.environ.get("GITHUB_WORKSPACE") or os.getcwd())
    args = parser.parse_args(argv)

    try:
        plan = resolve_plan(args.artifact_type)
    except UnsupportedArtifactType as exc:
        print(f"::error title=build-action::{exc}" if os.environ.get("GITHUB_ACTIONS") == "true" else f"ERROR: {exc}")
        return 1

    artifact_type = args.artifact_type.strip().lower()
    print(f"Building {artifact_type} artifact from {args.workspace}")
    for number, command in enumerate(plan, 1):
        print(f"MOCK step {number}: {command}")

    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"artifact_type={artifact_type}\nbuild_status=mocked\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(f"## Build ({artifact_type}), mocked\n\n" + "".join(f"1. `{c}`\n" for c in plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
