"""Dispatch, result_map integration and the GitHub output contract of main.py."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import ACTION_DIR, FIXTURES

import main


def run_action(**env_overrides):
    """Run main.py as GitHub Actions would and return (exit_code, outputs, stdout)."""
    with tempfile.TemporaryDirectory() as tmp:
        output_file = Path(tmp) / "output"
        output_file.touch()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PRCHECK_", "GITHUB_"))}
        env.update({"GITHUB_OUTPUT": str(output_file), "PYTHONIOENCODING": "utf-8"})
        env.update(env_overrides)
        proc = subprocess.run(
            [sys.executable, str(ACTION_DIR / "main.py")], env=env, capture_output=True, text=True
        )
        return proc.returncode, parse_github_output(output_file.read_text(encoding="utf-8")), proc.stdout


def parse_github_output(text):
    """Minimal parser for the $GITHUB_OUTPUT file format (key=value and heredoc)."""
    outputs, lines, i = {}, text.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if "<<" in line and ("=" not in line or line.index("<<") < line.index("=")):
            key, delimiter = line.split("<<", 1)
            i += 1
            value = []
            while lines[i] != delimiter:
                value.append(lines[i])
                i += 1
            outputs[key] = "\n".join(value)
        elif "=" in line:
            key, value = line.split("=", 1)
            outputs[key] = value
        i += 1
    return outputs


class DispatchTest(unittest.TestCase):
    def test_artifact_type_selects_validator(self):
        backend = main.run_checks(FIXTURES / "backend" / "pass", {"artifact_type": "backend"}, "{}")
        self.assertEqual(backend["artifact_consistency"]["artifact_type"], "backend")
        self.assertIn("distinct_artifact_ids", backend["artifact_consistency"]["details"])

        frontend = main.run_checks(
            FIXTURES / "frontend" / "pass", {"artifact_type": "Frontend ", "xml_path": "xyz"}, "{}"
        )
        self.assertEqual(frontend["artifact_consistency"]["artifact_type"], "frontend")
        self.assertIn("valid_files", frontend["artifact_consistency"]["details"])

    def test_unsupported_artifact_type_fails_clearly(self):
        result_map = main.run_checks(FIXTURES / "backend" / "pass", {"artifact_type": "mobile"}, "{}")
        entry = result_map["artifact_consistency"]
        self.assertIs(entry["passed"], False)
        self.assertIn("Unsupported artifact_type 'mobile'", entry["summary"])
        self.assertIn("backend, frontend", entry["summary"])
        self.assertTrue(main.compute_block_merge(result_map))

    def test_missing_artifact_type_fails(self):
        result_map = main.run_checks(FIXTURES / "backend" / "pass", {"artifact_type": ""}, "{}")
        self.assertIn("artifact_type is required", result_map["artifact_consistency"]["summary"])

    def test_existing_checks_are_preserved(self):
        incoming = json.dumps({"security_check": {"passed": True}})
        result_map = main.run_checks(FIXTURES / "backend" / "pass", {"artifact_type": "backend"}, incoming)
        self.assertEqual(set(result_map), {"security_check", "artifact_consistency"})
        self.assertFalse(main.compute_block_merge(result_map))

    def test_invalid_incoming_result_map_blocks(self):
        result_map = main.run_checks(FIXTURES / "backend" / "pass", {"artifact_type": "backend"}, "{oops")
        self.assertIs(result_map["result_map_input"]["passed"], False)
        self.assertTrue(main.compute_block_merge(result_map))

    def test_working_directory_cannot_escape_workspace(self):
        result_map = main.run_checks(
            FIXTURES / "backend" / "pass", {"artifact_type": "backend", "working_directory": "../mismatch"}, "{}"
        )
        self.assertIs(result_map["artifact_consistency"]["passed"], False)
        self.assertIn("outside the repository root", result_map["artifact_consistency"]["summary"])


class GitHubOutputContractTest(unittest.TestCase):
    def test_pass_publishes_block_merge_false(self):
        code, outputs, _ = run_action(
            GITHUB_WORKSPACE=str(FIXTURES / "backend" / "pass"), PRCHECK_ARTIFACT_TYPE="backend"
        )
        self.assertEqual(code, 0)
        self.assertEqual(outputs["block_merge"], "false")
        self.assertIs(json.loads(outputs["result_map"])["artifact_consistency"]["passed"], True)

    def test_fail_publishes_block_merge_true_and_exits_zero(self):
        # Exit 0: the verdict is enforced by pr_check.yml's gate step, so outputs are always published.
        code, outputs, _ = run_action(
            GITHUB_WORKSPACE=str(FIXTURES / "frontend" / "malformed"),
            PRCHECK_ARTIFACT_TYPE="frontend",
            PRCHECK_XML_PATH="xyz",
        )
        self.assertEqual(code, 0)
        self.assertEqual(outputs["block_merge"], "true")
        self.assertIs(json.loads(outputs["result_map"])["artifact_consistency"]["passed"], False)

    def test_working_directory_input(self):
        code, outputs, _ = run_action(
            GITHUB_WORKSPACE=str(FIXTURES),
            PRCHECK_WORKING_DIRECTORY="backend/mismatch",
            PRCHECK_ARTIFACT_TYPE="backend",
        )
        self.assertEqual(outputs["block_merge"], "true")

    def test_enforce_flag_for_local_runs(self):
        workspace = str(FIXTURES / "backend" / "mismatch")
        self.assertEqual(main.main(["--artifact-type", "backend", "--workspace", workspace, "--enforce"]), 1)
        self.assertEqual(main.main(["--artifact-type", "backend", "--workspace", workspace]), 0)


if __name__ == "__main__":
    unittest.main()
