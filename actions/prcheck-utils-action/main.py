#!/usr/bin/env python3
"""prcheck-utils-action entry point (MOCK of the organization's shared PR-check action).

Runs the PR checks for the checked-out repository, records each result in
``result_map`` and derives ``block_merge``. This mock registers one check,
``artifact_consistency``. The real framework's existing checks would register
alongside it in CHECKS, or arrive via the incoming result_map, and gate merging
the same way.

Inputs (environment variables set by action.yml, or CLI flags for local runs):
  PRCHECK_ARTIFACT_TYPE      backend | frontend                      (--artifact-type)
  PRCHECK_XML_PATH           XML directory, frontend only            (--xml-path)
  PRCHECK_RESULT_MAP         JSON result_map from earlier checks     (--result-map)
  PRCHECK_WORKING_DIRECTORY  scan root relative to the workspace     (--working-directory)
  GITHUB_WORKSPACE           checked-out repository                  (--workspace)

Outputs (written to $GITHUB_OUTPUT when running in GitHub Actions):
  result_map   compact JSON object keyed by check name
  block_merge  "true" | "false"

Exit code is 0 whenever a verdict was computed, including a failing one:
enforcement is the caller's job (the "Enforce merge gate" step in pr_check.yml),
so the outputs are always published. Use --enforce locally to exit 1 when
block_merge is true. An unexpected internal error still publishes
block_merge=true and exits 1.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable, Dict

from utils.backend_validator import validate_backend
from utils.frontend_validator import validate_frontend
from utils.fs_utils import PathConfigError, resolve_within
from utils.result_utils import (
    CheckResult,
    ResultMapError,
    compute_block_merge,
    failed_checks,
    parse_result_map,
    update_result_map,
)

ARTIFACT_CHECK_NAME = "artifact_consistency"

# artifact_type -> validator. Supporting a new artifact type means adding one entry here.
VALIDATORS: Dict[str, Callable[[Path, Dict[str, str]], CheckResult]] = {
    "backend": validate_backend,
    "frontend": validate_frontend,
}


def run_artifact_consistency(root: Path, config: Dict[str, str]) -> CheckResult:
    """Dispatch to the validator selected by the explicit artifact_type input."""
    artifact_type = (config.get("artifact_type") or "").strip().lower()
    supported = ", ".join(sorted(VALIDATORS))
    if not artifact_type:
        result = CheckResult.failure(f"artifact_type is required. Supported values: {supported}.")
    elif artifact_type not in VALIDATORS:
        result = CheckResult.failure(
            f"Unsupported artifact_type '{config.get('artifact_type')}'. Supported values: {supported}."
        )
    else:
        result = VALIDATORS[artifact_type](root, config)
    result.metadata["artifact_type"] = artifact_type or None
    return result


# check name -> runner. Every registered check contributes one result_map entry.
CHECKS: Dict[str, Callable[[Path, Dict[str, str]], CheckResult]] = {
    ARTIFACT_CHECK_NAME: run_artifact_consistency,
}


def run_checks(workspace: Path, config: Dict[str, str], incoming_result_map: str | None) -> Dict[str, Any]:
    """Run every registered check and return the accumulated result_map."""
    try:
        result_map = parse_result_map(incoming_result_map)
    except ResultMapError as exc:
        result_map = update_result_map({}, "result_map_input", CheckResult.failure(str(exc)))

    try:
        root = resolve_within(workspace, config.get("working_directory") or ".", "working_directory")
    except PathConfigError as exc:
        for name in CHECKS:
            result_map = update_result_map(result_map, name, CheckResult.failure(str(exc)))
        return result_map

    for name, check in CHECKS.items():
        result_map = update_result_map(result_map, name, check(root, config))
    return result_map


# --------------------------------------------------------------------------- GitHub I/O


def _escape_command_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_command_property(value: str) -> str:
    return _escape_command_data(value).replace(":", "%3A").replace(",", "%2C")


def write_outputs(result_map: Dict[str, Any], block_merge: bool) -> None:
    """Publish outputs via $GITHUB_OUTPUT (heredoc form, safe for any content)."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        return
    payload = json.dumps(result_map, separators=(",", ":"), sort_keys=True)
    delimiter = f"EOF_{uuid.uuid4().hex}"
    with open(output_file, "a", encoding="utf-8") as fh:
        fh.write(f"result_map<<{delimiter}\n{payload}\n{delimiter}\n")
        fh.write(f"block_merge={'true' if block_merge else 'false'}\n")


def emit_annotations(result_map: Dict[str, Any], working_directory: str) -> None:
    """Emit workflow-command annotations so failures show on the PR's Checks tab."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    prefix = Path(working_directory or ".")
    title = lambda name: _escape_command_property(f"PR check: {name}")  # noqa: E731
    for name in failed_checks(result_map):
        entry = result_map.get(name)
        errors = entry.get("errors") if isinstance(entry, dict) else None
        for error in errors or [f"check '{name}' did not pass"]:
            # File-specific errors are formatted "<path relative to scan root>: <reason>".
            head, sep, _ = str(error).partition(": ")
            file_part = ""
            if sep and head.endswith(".xml") and " " not in head:
                file_part = f"file={_escape_command_property((prefix / head).as_posix())},"
            print(f"::error {file_part}title={title(name)}::{_escape_command_data(str(error))}")


def write_step_summary(result_map: Dict[str, Any], block_merge: bool) -> None:
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return
    lines = [
        "## PR checks (prcheck-utils-action)",
        "",
        "| Check | Required | Result | Summary |",
        "|---|---|---|---|",
    ]
    for name, entry in sorted(result_map.items()):
        entry = entry if isinstance(entry, dict) else {}
        required = "no" if entry.get("required", True) is False else "yes"
        verdict = "PASS" if entry.get("passed") is True else "FAIL"
        summary = str(entry.get("summary", "")).replace("|", "\\|")
        lines.append(f"| `{name}` | {required} | {verdict} | {summary} |")
    lines += ["", f"**block_merge = `{'true' if block_merge else 'false'}`**", ""]
    for name in failed_checks(result_map):
        entry = result_map.get(name)
        for error in (entry.get("errors") if isinstance(entry, dict) else None) or []:
            lines.append(f"- `{name}`: {error}")
    with open(summary_file, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def print_report(result_map: Dict[str, Any], block_merge: bool) -> None:
    print("result_map:")
    print(json.dumps(result_map, indent=2, sort_keys=True))
    blocking = failed_checks(result_map)
    if block_merge:
        print(f"block_merge=true (failed required checks: {', '.join(blocking) or 'none recorded'})")
    else:
        print("block_merge=false (all required checks passed)")


# --------------------------------------------------------------------------- entry point


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    env = os.environ
    parser = argparse.ArgumentParser(description="Run organization PR checks and compute block_merge.")
    parser.add_argument("--artifact-type", default=env.get("PRCHECK_ARTIFACT_TYPE", ""))
    parser.add_argument("--xml-path", default=env.get("PRCHECK_XML_PATH", ""))
    parser.add_argument("--result-map", default=env.get("PRCHECK_RESULT_MAP", "{}"))
    parser.add_argument("--working-directory", default=env.get("PRCHECK_WORKING_DIRECTORY", "."))
    parser.add_argument("--workspace", default=env.get("GITHUB_WORKSPACE") or os.getcwd())
    parser.add_argument("--enforce", action="store_true", help="exit 1 when block_merge is true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = {
        "artifact_type": args.artifact_type,
        "xml_path": args.xml_path,
        "working_directory": args.working_directory,
    }
    try:
        result_map = run_checks(Path(args.workspace), config, args.result_map)
    except Exception:  # fail safe: never let a crash look like a pass
        traceback.print_exc()
        result_map = {ARTIFACT_CHECK_NAME: CheckResult.failure("Internal error in prcheck-utils-action; see log.").to_dict()}
        write_outputs(result_map, True)
        return 1

    block_merge = compute_block_merge(result_map)
    print_report(result_map, block_merge)
    write_outputs(result_map, block_merge)
    write_step_summary(result_map, block_merge)
    emit_annotations(result_map, args.working_directory)
    return 1 if (args.enforce and block_merge) else 0


if __name__ == "__main__":
    sys.exit(main())
