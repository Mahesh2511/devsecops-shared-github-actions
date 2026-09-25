# Requirements traceability

Every requirement from the four source documents, mapped to where it's implemented and how it was verified.

**Sources:** **PDF** is `Exercise.pdf`. **CL** is the reviewer's clarification (`clarification on exercise.txt`). **SP** is `spec.md`. **IMG** is `image.png`.
**Status:** ✅ met and verified · ⚠️ met, with a documented deviation or caveat.
**Evidence links:** [backend PR #1](https://github.com/Mahesh2511/backend-sample/pull/1) · [frontend PR #1](https://github.com/Mahesh2511/frontend-sample/pull/1) · [Framework CI](https://github.com/Mahesh2511/devsecops-shared-github-actions/actions/workflows/ci.yml)

---

## 1. Exercise PDF

### 1.1 Objective and workflow file (PDF §1)

| # | Requirement | Status | Where / how |
|---|---|---|---|
| P1 | Write **one** workflow file, not two, for backend and frontend | ✅ | [`templates/consumer-build.yml`](../templates/consumer-build.yml) is the single file. Both sample repos use it verbatim except for the `with:` values |
| P2 | Triggers on pull requests | ✅ | `on: pull_request` (plus `workflow_dispatch` for manual demos) |
| P3 | Calls the shared `build.yml` reusable workflow | ✅ | `uses: Mahesh2511/devsecops-shared-github-actions/.github/workflows/build.yml@v1` |
| P4 | Supports both backend and frontend repos through the same file | ✅ | Verified on GitHub: both repos' runs pass through the same shared chain |
| P5 | Explain the input that says backend vs frontend | ✅ | `artifact_type` (required, `backend`\|`frontend`) plus `xml_path` (frontend). See [README](../README.md#using-it-from-a-consumer-repository) and [architecture.md § Input propagation](architecture.md#input-propagation) |
| P6 | Explain how the input flows: workflow → build.yml → pr_check.yml → action | ✅ | [end-to-end-guide.md § 3](end-to-end-guide.md#3-one-pr-step-by-step), steps 1 to 5, and the architecture.md table. Each hop forwards it unchanged via `with:`; the action reads it through env vars |

### 1.2 Relevant build.yml steps (PDF §2)

| # | Requirement | Status | Where / how |
|---|---|---|---|
| P7 | Where the PR check runs relative to the build | ✅ | `build.yml` job `pr-check` (line 35) runs first. Job `build` (line 49) has `needs: pr-check` |
| P8 | Where source code is checked out, before validation | ✅ | `pr_check.yml` step `Checkout source` (line 40), the first step, before the action |
| P9 | Where and how a failed check blocks the build (merge gating) | ✅ | `pr_check.yml` step `Enforce merge gate` (line 64) fails the job. `build.yml` `needs` plus `if:` (lines 51–52) skip the build. Branch protection's required check blocks the merge. See [architecture.md § touchpoints](architecture.md#where-the-new-logic-plugs-into-buildyml) |

### 1.3 PR check logic (PDF §3)

| # | Requirement | Status | Where / how |
|---|---|---|---|
| P10 | New PR check step/handler, with rules per artifact type | ✅ | `artifact_consistency` registered in `CHECKS`. `VALIDATORS` dispatches by type in `main.py` |
| P11 | Backend: traverse **all** `pom.xml` | ✅ | `find_files()` recursive walk, [`backend_validator.py`](../actions/prcheck-utils-action/utils/backend_validator.py). Test: `test_scan_is_recursive_and_layout_independent` |
| P12 | Backend: extract `artifactId` from each | ✅ | `extract_artifact_id()`: the direct child of `<project>`, namespace-aware |
| P13 | Backend: do all values match? true/false | ✅ | Grouped by ID; exactly one group → `passed=True`. GitHub: backend PR #1 ❌ (mismatch), `main` ✅ |
| P14 | Frontend: traverse all `.xml` in a given path (e.g. `xyz`) | ✅ | `xml_path` input, recursive, case-insensitive `.xml`. The fixture uses `xyz`; the sample uses `config` |
| P15 | Frontend: every file well-formed? true/false | ✅ | `ET.parse` per file; `invalid_files` has line and column. GitHub: frontend PR #1 ❌ then ✅ |

### 1.4 Decision factor (PDF §4)

| # | Requirement | Status | Where / how |
|---|---|---|---|
| P16 | true/false decides whether the PR check passes or fails | ✅ | `passed` → `compute_block_merge()` → gate step exit code. See [architecture.md § Decision factor](architecture.md#decision-factor-truefalse--passfail--merge) |
| P17 | Ties into the **existing** block-merge gating used by other checks | ✅ | The result is one entry in the shared `result_map`. `block_merge` is computed over all entries; prior checks arrive via the `result_map` input. Tests: `test_existing_checks_are_preserved`, `test_existing_failure_still_blocks_even_if_artifact_check_passes` |

### 1.5 Deliverables (PDF)

| # | Deliverable | Status | Where |
|---|---|---|---|
| D1 | The workflow YAML file | ✅ | `templates/consumer-build.yml`; also `backend-sample` and `frontend-sample` `.github/workflows/build.yml` |
| D2 | Short explanation of the build.yml steps touched or depended on | ✅ | [architecture.md § Where the new logic plugs into build.yml](architecture.md#where-the-new-logic-plugs-into-buildyml) |
| D3 | Pseudocode or code for the validation (backend + frontend) | ✅ | Working Python: `backend_validator.py`, `frontend_validator.py`. 36 unit tests |
| D4 | How the result feeds the pass/fail decision | ✅ | [architecture.md § Decision factor](architecture.md#decision-factor-truefalse--passfail--merge), [end-to-end-guide.md steps 7–10](end-to-end-guide.md) |
| D5 | Shared via GitHub.com | ✅ | Three public repos under https://github.com/Mahesh2511 |

---

## 2. Reviewer clarification (CL)

| # | Requirement / hint | Status | Where / how |
|---|---|---|---|
| C1 | Assume the private components exist; build reasonable mocks | ✅ | `build.yml`, `pr_check.yml`, `prcheck-utils-action`, `build-action`, each marked `MOCK` in its header |
| C2 | Clearly document the assumed interfaces and behaviours | ✅ | [assumptions.md](assumptions.md): input/output tables for all four components, the mocked-behaviour table and interpretation decisions |
| C3 | Single workflow using an input like `artifact_type` | ✅ | P1, P5 |
| C4 | Pass the input workflow → build.yml → pr_check.yml → action | ✅ | P6. actionlint verifies the build.yml → pr_check.yml input contract |
| C5 | Run PR validation before the build | ✅ | P7. GitHub: the build is `skipped` whenever the PR check fails |
| C6 | Backend: scan all pom.xml, extract artifactId, all must match | ✅ | P11–P13 |
| C7 | Frontend: scan XML files in a configured path, validate well-formedness | ✅ | P14–P15 |
| C8 | Update `result_map` | ✅ | `update_result_map()`; published as a job output and in the job summary |
| C9 | Set `block_merge=true` when validation fails | ✅ | `compute_block_merge()`. Test `test_fail_publishes_block_merge_true_and_exits_zero`; GitHub logs `block_merge=true` |
| C10 | Build job depends on successful PR checks | ✅ | `needs: pr-check` plus `if: … result == 'success' && block_merge == 'false'` |
| C11 | Evaluation focus: design, GitHub Actions knowledge, integration reasoning | ✅ | [architecture.md](architecture.md), [reviewer-guide.md](reviewer-guide.md) |

---

## 3. Diagram (IMG)

| Box in `image.png` | Status | Implemented as |
|---|---|---|
| Repo, **backend** | ✅ | `Mahesh2511/backend-sample` |
| Repo, **frontend** | ✅ | `Mahesh2511/frontend-sample` |
| **Shared Library** | ✅ | `Mahesh2511/devsecops-shared-github-actions` |
| Workflow → **build.yml** | ✅ | `.github/workflows/build.yml` |
| Workflow → **pr_check.yml** | ✅ | `.github/workflows/pr_check.yml` |
| Actions → **build Action** | ✅ | `actions/build-action/`, called by the `build` job (added in `v1.1.0` to match the diagram) |
| Actions → **PR_check action** | ✅ | `actions/prcheck-utils-action/` |
| **Action.yml / Utils / main.py** | ✅ | Both actions follow it: `action.yml`, `utils/`, `main.py` |

---

## 4. spec.md acceptance criteria (SP §20)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| A1 | One consumer workflow design supports backend and frontend | ✅ | P1, P4 |
| A2 | `artifact_type` explicitly configurable | ✅ | Required input; never inferred |
| A3 | Frontend XML path configurable | ✅ | `xml_path`. Test `test_path_is_configurable` (`ui/resources`) |
| A4 | Consumer calls reusable `build.yml` | ✅ | P3 |
| A5 | `build.yml` passes inputs to `pr_check.yml` | ✅ | `build.yml` lines 37–40 |
| A6 | `pr_check.yml` passes inputs to the action | ✅ | `pr_check.yml` lines 54–57 |
| A7 | Source checkout before validation | ✅ | P8 |
| A8 | Backend validator recursively scans all `pom.xml` | ✅ | P11. The fixture has a POM 4 levels deep |
| A9 | Backend validator extracts and compares `artifactId` | ✅ | P12–P13 |
| A10 | Frontend validator recursively scans the configured path | ✅ | Fixture `xyz/nested/settings.xml` |
| A11 | Frontend validator checks well-formedness | ✅ | P15 |
| A12 | Result added to `result_map` | ✅ | C8 |
| A13 | Failed validation → `block_merge=true` | ✅ | C9 |
| A14 | PR-check job fails when merge must be blocked | ✅ | Gate step. GitHub: `build / PR Check / PR checks` = failure on both demo PRs |
| A15 | Build depends on successful PR checks | ✅ | C10. GitHub: `build / Build` = skipped on failure |
| A16 | No duplicated validation logic in consumers | ✅ | Consumers contain only `build.yml` plus sample data |
| A17 | No repo-specific paths or IDs in shared logic | ✅ | A grep audit of `actions/` and workflows found no `xyz`, `config`, `sample-service`, or module or repo names |
| A18 | Mock interfaces documented | ✅ | C2 |
| A19 | PASS and FAIL scenarios demonstrated | ✅ | [test-scenarios.md](test-scenarios.md): local, CI and GitHub PRs |
| A20 | Structure suitable for future validators and checks | ✅ | `VALIDATORS` / `CHECKS` / `BUILD_PLANS` registries, `required` flag. See [architecture.md § Extending](architecture.md#extending-the-framework) |

## 5. spec.md design rules (SP §5–§18)

| # | Rule | Status | Where / how |
|---|---|---|---|
| S1 | Consumer workflow intentionally thin | ✅ | 14–15 lines, no logic |
| S2 | `xml_path` required only for frontend; don't hard-code `xyz` | ✅ | Default `""`; frontend without it fails with "xml_path is required" |
| S3 | Interface extensible without changing consumer structure | ✅ | New optional inputs with defaults; registries |
| S4 | Actual build may be mocked | ✅ | `build-action` prints the per-type plan |
| S5 | pr_check.yml outputs `result_map`, `block_merge` | ✅ | `on.workflow_call.outputs`, forwarded by build.yml as well |
| S6 | Action selects the validator by `artifact_type`; unknown types fail clearly | ✅ | U1 in the test matrix. GitHub CI scenario `unsupported-type` |
| S7 | Backend: no POMs → fail; empty `artifactId` → fail; ignore unrelated elements; diagnostics | ✅ | B4–B7. `details` has files_inspected, artifact_ids, files_by_artifact_id |
| S8 | Frontend: path must exist; no XML → fail; diagnostics (valid, invalid, errors) | ✅ | F5–F7. `details` has files_inspected, valid_files, invalid_files |
| S9 | `result_map` generic and able to hold future checks | ✅ | Keyed by check name. Test R1 |
| S10 | `block_merge` = any required check fails | ✅ | `compute_block_merge()` plus fail-safe cases (R3) |
| S11 | Document that an output alone doesn't enforce merge protection | ✅ | README § How it works, architecture.md, `pr_check.yml` comments. **Also configured**: branch protection on both samples |
| S12 | A failed PR check can't accidentally allow the build | ✅ | `needs` plus an explicit `block_merge == 'false'` guard |
| S13 | Don't re-detect the type by repo name, path or branch | ✅ | Only `artifact_type` is read |
| S14 | Versioning: consumers pin a tag, not `@main` | ✅ | `@v1`; releases `v1.0.0`, `v1.0.1`, `v1.1.0` |
| S15 | Error handling: unsupported type, missing xml_path, missing path, no files, malformed POM/XML, missing artifactId | ✅ | U1, F6, F5, B7/F7, B6/F4, B4 |
| S16 | Configuration/parse errors never become success | ✅ | All error paths set `passed=False`; a crash still publishes `block_merge=true` |
| S17 | Sample projects: Maven parent with `service-a`/`service-b`; frontend `config/*.xml` | ⚠️ | Built as specified. **Caveat:** real Maven rejects modules that share one artifactId (verified with Maven 3.9.16). See [assumptions.md](assumptions.md), decision 2 |
| S18 | Samples aren't special cases (no hard-coded sample names or paths) | ✅ | A17 |
| S19 | Docs: README, architecture, assumptions, test-scenarios | ⚠️ | All present. **Deviation:** they live in `shared-devsecops/docs/` rather than the exercise root, because the root isn't a published repository |
| S20 | Validate YAML and Python syntax | ✅ | actionlint 1.7.12 is clean; `compileall` runs in CI; 36 tests |
| S21 | Don't add unrelated validators | ✅ | Only `artifact_consistency`; existing checks are represented by the `result_map` input |

---

## 6. Beyond the requirements

| Addition | Why |
|---|---|
| Branch protection on both sample `main` branches | Shows that the merge really is blocked, not just described |
| Framework CI (`ci.yml`): unit tests, 11 real-action scenarios, 2 build-action runs | The shared library tests itself before each release |
| Job summary table and `::error file=…::` annotations | Reviewers see why a check failed directly on the PR |
| Path-traversal protection for `xml_path` / `working_directory` | Inputs are treated as untrusted |
| `working_directory` action input | Monorepo support; lets CI point the action at fixtures |
| Static `Build` job name (`v1.0.1`) | A skipped job's name isn't evaluated; a stable name is needed for required checks |
