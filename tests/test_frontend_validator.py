import unittest

from support import FIXTURES

from utils.frontend_validator import validate_frontend

FRONTEND = FIXTURES / "frontend"


class FrontendValidatorTest(unittest.TestCase):
    def test_pass_when_all_xml_well_formed(self):
        result = validate_frontend(FRONTEND / "pass", {"xml_path": "xyz"})
        self.assertTrue(result.passed, result.errors)
        self.assertEqual(
            result.details["files_inspected"],
            ["xyz/application.xml", "xyz/config.xml", "xyz/nested/settings.xml"],
        )

    def test_only_configured_path_and_xml_files_are_scanned(self):
        # pass/outside.xml is malformed but outside xml_path; notes.json is not XML.
        result = validate_frontend(FRONTEND / "pass", {"xml_path": "xyz"})
        self.assertTrue(result.passed)
        self.assertNotIn("outside.xml", result.details["files_inspected"])
        self.assertFalse(any(f.endswith(".json") for f in result.details["files_inspected"]))

    def test_path_is_configurable(self):
        result = validate_frontend(FRONTEND / "custom_path", {"xml_path": "ui/resources"})
        self.assertTrue(result.passed, result.errors)
        self.assertEqual(
            result.details["files_inspected"],
            ["ui/resources/i18n/de.xml", "ui/resources/strings.xml"],
        )

    def test_fail_when_one_xml_malformed(self):
        result = validate_frontend(FRONTEND / "malformed", {"xml_path": "xyz"})
        self.assertFalse(result.passed)
        self.assertEqual([i["file"] for i in result.details["invalid_files"]], ["xyz/application.xml"])
        self.assertEqual(len(result.details["valid_files"]), 2)
        self.assertIn("line", result.details["invalid_files"][0]["error"])

    def test_fail_when_path_missing(self):
        result = validate_frontend(FRONTEND / "pass", {"xml_path": "does-not-exist"})
        self.assertFalse(result.passed)
        self.assertIn("does not exist", result.summary)

    def test_fail_when_xml_path_not_provided(self):
        result = validate_frontend(FRONTEND / "pass", {"xml_path": ""})
        self.assertFalse(result.passed)
        self.assertIn("xml_path is required", result.summary)

    def test_fail_when_no_xml_files(self):
        result = validate_frontend(FRONTEND / "empty", {"xml_path": "xyz"})
        self.assertFalse(result.passed)
        self.assertIn("No .xml files found", result.summary)

    def test_fail_when_path_is_a_file(self):
        result = validate_frontend(FRONTEND / "pass", {"xml_path": "outside.xml"})
        self.assertFalse(result.passed)
        self.assertIn("not a directory", result.summary)

    def test_fail_when_path_escapes_repository(self):
        for bad in ("../malformed/xyz", "/etc"):
            with self.subTest(xml_path=bad):
                result = validate_frontend(FRONTEND / "pass", {"xml_path": bad})
                self.assertFalse(result.passed)
                self.assertIn("outside the repository root", result.summary)


if __name__ == "__main__":
    unittest.main()
