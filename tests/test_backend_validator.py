import unittest

from support import FIXTURES

from utils.backend_validator import validate_backend

BACKEND = FIXTURES / "backend"


class BackendValidatorTest(unittest.TestCase):
    def test_pass_when_all_artifact_ids_match(self):
        result = validate_backend(BACKEND / "pass", {})
        self.assertTrue(result.passed, result.errors)
        self.assertEqual(result.details["distinct_artifact_ids"], ["orders-api"])

    def test_scan_is_recursive_and_layout_independent(self):
        result = validate_backend(BACKEND / "pass", {})
        self.assertEqual(
            result.details["files_inspected"],
            ["core/pom.xml", "legacy/pom.xml", "libs/deep/nested/impl/pom.xml", "pom.xml"],
        )

    def test_parent_and_dependency_artifact_ids_are_ignored(self):
        # Module POMs in the PASS fixture reference a *different* parent artifactId
        # and an unrelated dependency; only the project's own artifactId counts.
        result = validate_backend(BACKEND / "pass", {})
        self.assertTrue(result.passed)
        self.assertNotIn("different-parent-id", result.details["distinct_artifact_ids"])
        self.assertNotIn("unrelated-lib", result.details["distinct_artifact_ids"])

    def test_fail_when_one_artifact_id_differs(self):
        result = validate_backend(BACKEND / "mismatch", {})
        self.assertFalse(result.passed)
        self.assertEqual(result.details["distinct_artifact_ids"], ["billing-api", "orders-api"])
        self.assertEqual(result.details["files_by_artifact_id"]["billing-api"], ["module-b/pom.xml"])
        self.assertTrue(any("mismatch" in e for e in result.errors))

    def test_fail_when_artifact_id_missing(self):
        result = validate_backend(BACKEND / "missing_artifact_id", {})
        self.assertFalse(result.passed)
        self.assertTrue(any(e.startswith("module-a/pom.xml: no project-level <artifactId>") for e in result.errors))

    def test_fail_when_pom_malformed(self):
        result = validate_backend(BACKEND / "malformed", {})
        self.assertFalse(result.passed)
        self.assertTrue(any(e.startswith("module-a/pom.xml: malformed XML") for e in result.errors))

    def test_fail_when_no_pom_found(self):
        result = validate_backend(BACKEND / "no_pom", {})
        self.assertFalse(result.passed)
        self.assertIn("No pom.xml files found", result.summary)

    def test_fail_on_empty_artifact_id_and_non_pom_root(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pom.xml").write_text("<project><artifactId>  </artifactId></project>")
            (root / "sub").mkdir()
            (root / "sub" / "pom.xml").write_text("<settings><artifactId>x</artifactId></settings>")
            result = validate_backend(root, {})
        self.assertFalse(result.passed)
        joined = "\n".join(result.errors)
        self.assertIn("pom.xml: <artifactId> is present but empty", joined)
        self.assertIn("sub/pom.xml: not a Maven POM", joined)


if __name__ == "__main__":
    unittest.main()
