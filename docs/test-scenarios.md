# Test scenarios

Scenarios are covered at three levels:

1. **Unit tests** (`tests/`, `python -m unittest discover -s tests -v`) cover the validators, result_map, block_merge and the `$GITHUB_OUTPUT` contract.
2. **Action scenarios** (`.github/workflows/ci.yml`, job `action-scenarios`) run the real composite action on GitHub against the fixtures in `tests/fixtures/` and assert `block_merge`.
3. **End-to-end PRs** in `backend-sample` and `frontend-sample` exercise the full chain: consumer → build.yml → pr_check.yml → action → gate → build.

## Scenario matrix

| # | Scenario | artifact_type | Condition | Expected result_map / gate | Fixture / test |
|---|---|---|---|---|---|
| B1 | Backend valid | backend | All project `artifactId` values match, at arbitrary depth, namespaced or not | `passed=true`, `block_merge=false`, build runs | `backend/pass`; `test_pass_when_all_artifact_ids_match` |
| B2 | Backend ignores unrelated IDs | backend | `<parent>` and `<dependency>` artifactIds differ from the project ID | still PASS | `backend/pass`; `test_parent_and_dependency_artifact_ids_are_ignored` |
| B3 | Backend mismatch | backend | One module declares a different artifactId | `passed=false`, `block_merge=true`, build skipped | `backend/mismatch`; `test_fail_when_one_artifact_id_differs` |
| B4 | Backend missing artifactId | backend | A POM has no project-level `<artifactId>` | FAIL, file named in error | `backend/missing_artifact_id` |
| B5 | Backend empty artifactId / not a POM | backend | `<artifactId> </artifactId>`, or root element isn't `<project>` | FAIL | `test_fail_on_empty_artifact_id_and_non_pom_root` |
| B6 | Backend malformed POM | backend | Unclosed element | FAIL with line/column | `backend/malformed` |
| B7 | Backend no POM | backend | Repository contains no `pom.xml` | FAIL (misconfiguration, not a vacuous pass) | `backend/no_pom` |
| F1 | Frontend valid | frontend | Every `*.xml` under `xml_path` parses | `passed=true`, `block_merge=false` | `frontend/pass` (`xml_path=xyz`) |
| F2 | Frontend scope | frontend | Malformed XML *outside* `xml_path` and non-XML files inside it | ignored, still PASS | `test_only_configured_path_and_xml_files_are_scanned` |
| F3 | Frontend configurable path | frontend | XML under `ui/resources` | validator uses the supplied path | `frontend/custom_path`; `test_path_is_configurable` |
| F4 | Frontend malformed | frontend | One file has an unclosed element | FAIL; `invalid_files` lists only that file | `frontend/malformed` |
| F5 | Frontend path missing | frontend | `xml_path` doesn't exist | FAIL "does not exist" | `test_fail_when_path_missing` |
| F6 | Frontend xml_path not provided | frontend | `xml_path=""` | FAIL "xml_path is required" | `test_fail_when_xml_path_not_provided` |
| F7 | Frontend no XML files | frontend | Directory has no `*.xml` | FAIL | `frontend/empty` |
| F8 | Frontend path escapes repo | frontend | `../x` or `/etc` | FAIL "outside the repository root" | `test_fail_when_path_escapes_repository` |
| U1 | Unsupported type | `mobile` | Unknown artifact_type | FAIL listing `backend, frontend` | `test_unsupported_artifact_type_fails_clearly` |
| U2 | Missing type | `""` | Empty artifact_type | FAIL "artifact_type is required" | `test_missing_artifact_type_fails` |
| R1 | Existing checks preserved | backend | Incoming `result_map` has `security_check` | Both keys present | `test_existing_checks_are_preserved` |
| R2 | Other failing check still blocks | any | `security_check.passed=false`, artifact passes | `block_merge=true` | `test_existing_failure_still_blocks_even_if_artifact_check_passes` |
| R3 | Fail-safe gating | any | Entry missing `passed`, `"true"` string, `null`, empty map | `block_merge=true` | `test_fail_safe_on_ambiguous_entries` |
| R4 | Output contract | both | Pass and fail runs | `$GITHUB_OUTPUT` has `result_map` (JSON) and `block_merge`; exit 0 | `GitHubOutputContractTest` |

## End-to-end demonstration on GitHub

After the three repositories are published and `v1` is tagged on the shared repo:

| Step | Repo | Change in a PR | Expected on the PR |
|---|---|---|---|
| E1 | backend-sample | Any harmless change (README) | `PR Check` ✅ → `Build (backend)` ✅ |
| E2 | backend-sample | `service-b/pom.xml`: project `artifactId` → `another-service` | `PR Check` ❌ (`artifactId mismatch … 'another-service' in service-b/pom.xml`), `Build` **skipped**; merge blocked if required |
| E3 | frontend-sample | Any harmless change | `PR Check` ✅ → `Build (frontend)` ✅ |
| E4 | frontend-sample | Break `config/settings.xml` (remove a closing tag) | `PR Check` ❌ with annotation on `config/settings.xml`, `Build` **skipped** |
| E5 | frontend-sample | Revert E4 on the same PR | Check goes green again, build runs |

To enforce blocking: *Settings → Branches (or Rules) → require status check* `build / PR Check / PR checks` on `main`.

## Local run results (pre-publish)

```
$ python -m unittest discover -s tests
Ran 33 tests ... OK

$ python actions/prcheck-utils-action/main.py --artifact-type backend --workspace ../backend-sample --enforce
block_merge=false (all required checks passed)                        exit 0

$ python actions/prcheck-utils-action/main.py --artifact-type frontend --xml-path config --workspace ../frontend-sample --enforce
block_merge=false (all required checks passed)                        exit 0

# copy of backend-sample with service-b artifactId changed
"artifactId mismatch: 2 distinct values found: 'another-service' in service-b/pom.xml; 'sample-service' in pom.xml, service-a/pom.xml"
block_merge=true (failed required checks: artifact_consistency)        exit 1

# copy of frontend-sample with settings.xml broken
"config/settings.xml: mismatched tag: line 8, column 2"
block_merge=true (failed required checks: artifact_consistency)        exit 1
```

All workflow files also pass `actionlint` 1.7.12, which checks `build.yml` → `pr_check.yml` inputs and outputs across the local reusable-workflow call.
