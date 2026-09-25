import unittest

import support  # noqa: F401  (sys.path setup)

from utils.result_utils import (
    CheckResult,
    ResultMapError,
    compute_block_merge,
    failed_checks,
    parse_result_map,
    update_result_map,
)


class ResultMapTest(unittest.TestCase):
    def test_artifact_check_is_added_alongside_existing_checks(self):
        existing = {"security_check": {"passed": True}, "dependency_check": {"passed": True}}
        updated = update_result_map(existing, "artifact_consistency", CheckResult(passed=False, summary="x"))
        self.assertEqual(set(updated), {"security_check", "dependency_check", "artifact_consistency"})
        self.assertIs(updated["artifact_consistency"]["passed"], False)
        self.assertNotIn("artifact_consistency", existing, "input map must not be mutated")

    def test_block_merge_false_only_when_all_required_pass(self):
        self.assertFalse(compute_block_merge({"a": {"passed": True}, "b": {"passed": True}}))
        self.assertTrue(compute_block_merge({"a": {"passed": True}, "b": {"passed": False}}))

    def test_existing_failure_still_blocks_even_if_artifact_check_passes(self):
        result_map = update_result_map(
            {"security_check": {"passed": False}}, "artifact_consistency", CheckResult(passed=True, summary="ok")
        )
        self.assertTrue(compute_block_merge(result_map))
        self.assertEqual(failed_checks(result_map), ["security_check"])

    def test_non_required_failures_do_not_block(self):
        self.assertFalse(compute_block_merge({"a": {"passed": True}, "lint": {"passed": False, "required": False}}))

    def test_fail_safe_on_ambiguous_entries(self):
        for bad in ({}, {"a": {}}, {"a": {"passed": "true"}}, {"a": None}, {"a": {"passed": 1}}):
            with self.subTest(result_map=bad):
                self.assertTrue(compute_block_merge(bad))

    def test_parse_result_map(self):
        self.assertEqual(parse_result_map(""), {})
        self.assertEqual(parse_result_map('{"a": {"passed": true}}'), {"a": {"passed": True}})
        with self.assertRaises(ResultMapError):
            parse_result_map("not json")
        with self.assertRaises(ResultMapError):
            parse_result_map("[1, 2]")


if __name__ == "__main__":
    unittest.main()
