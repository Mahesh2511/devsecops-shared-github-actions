"""build-action runs as a subprocess: its main/utils module names match prcheck-utils-action's."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import REPO_ROOT

BUILD_MAIN = REPO_ROOT / "actions" / "build-action" / "main.py"


def run_build(artifact_type):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "output"
        out.touch()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BUILD_", "GITHUB_"))}
        env.update({"GITHUB_OUTPUT": str(out), "BUILD_ARTIFACT_TYPE": artifact_type})
        proc = subprocess.run([sys.executable, str(BUILD_MAIN)], env=env, capture_output=True, text=True)
        return proc.returncode, proc.stdout, out.read_text()


class BuildActionTest(unittest.TestCase):
    def test_backend_plan(self):
        code, stdout, outputs = run_build("backend")
        self.assertEqual(code, 0)
        self.assertIn("mvn -B -ntp verify", stdout)
        self.assertIn("artifact_type=backend", outputs)

    def test_frontend_plan(self):
        code, stdout, outputs = run_build(" Frontend ")
        self.assertEqual(code, 0)
        self.assertIn("npm run build", stdout)
        self.assertIn("artifact_type=frontend", outputs)

    def test_unsupported_type_fails(self):
        code, stdout, outputs = run_build("mobile")
        self.assertEqual(code, 1)
        self.assertIn("Unsupported artifact_type 'mobile'", stdout)
        self.assertEqual(outputs, "")


if __name__ == "__main__":
    unittest.main()
