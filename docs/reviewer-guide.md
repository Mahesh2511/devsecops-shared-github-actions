# Reviewer guide

This is a guided 15-minute review of the *PR Check Artifact Validation* exercise. It answers the exercise's four questions in order, links straight to the code, and points to live evidence on GitHub.

| | |
|---|---|
| **Shared library** | https://github.com/Mahesh2511/devsecops-shared-github-actions (use tag `v1` -> `v1.1.0`) |
| **Consumers** | https://github.com/Mahesh2511/backend-sample, https://github.com/Mahesh2511/frontend-sample |
| **Live failure demo** | [backend-sample PR #1](https://github.com/Mahesh2511/backend-sample/pull/1): check fails, build skipped, merge **BLOCKED** |
| **Live fix demo** | [frontend-sample PR #1](https://github.com/Mahesh2511/frontend-sample/pull/1): commit 1 fails, commit 2 passes with the build running |
| **Mock notice** | The internal `build.yml`, `pr_check.yml` and `prcheck-utils-action` weren't available. They're mocked against documented interfaces in [assumptions.md](assumptions.md) |

---

## Suggested review path

| Min | Look at | What to check |
|---|---|---|
| 2 | [`templates/consumer-build.yml`](../templates/consumer-build.yml) | Exercise Q1: one file, `on: pull_request`, calls `build.yml@v1`, and `artifact_type` selects the behaviour |
| 3 | [`.github/workflows/build.yml`](../.github/workflows/build.yml) | Exercise Q2: `pr-check` job first; `build` job with `needs` plus the `if:` guard; build-action |
| 2 | [`.github/workflows/pr_check.yml`](../.github/workflows/pr_check.yml) | Q2: `[1]` checkout -> `[2]` action -> `[3]` merge gate (the numbered comments) |
| 4 | [`actions/prcheck-utils-action/`](../actions/prcheck-utils-action) | Q3: `main.py` dispatch (`VALIDATORS`, `CHECKS`); `utils/backend_validator.py`; `utils/frontend_validator.py` |
| 2 | [`utils/result_utils.py`](../actions/prcheck-utils-action/utils/result_utils.py) | Q4: `compute_block_merge()`, the whole decision rule in about 15 lines |
| 2 | backend-sample PR #1 -> *Checks* -> *PR checks* | Real output: error annotation, job summary table, `Build` skipped, merge box blocked |

---

## The exercise's four questions: short answers

### Q1. One workflow file for backend and frontend

* **The input:** `artifact_type` (`backend` | `frontend`) plus `xml_path` for frontend. It's an explicit declaration, and the type is never inferred from the repo name, path or branch.
* **How it flows:** consumer `with:` -> `build.yml` `inputs` -> `pr_check.yml` `with:` -> action `with:` -> `main.py` (as env vars) -> `VALIDATORS[artifact_type]`. Every hop forwards it unchanged.
* **Validation:** `workflow_call` inputs can't declare an enum, so the value is validated once, in the action. An invalid value fails the PR check and the build never runs.

### Q2. The build.yml touchpoints

| Concern | Location |
|---|---|
| PR check before the build | `build.yml` job `pr-check` (L35) -> job `build` has `needs: pr-check` (L51) |
| Checkout before validation | `pr_check.yml` step `Checkout source` (L40), which checks out the *consumer* repo at the PR merge ref |
| Where a failure blocks | `pr_check.yml` `Enforce merge gate` (L64) fails the job -> `build` is skipped (`needs` plus `if:` at L52). The *merge* is blocked by a required status check on `build / PR Check / PR checks` |

### Q3. The check logic

* **Backend:** a recursive `**/pom.xml` scan. It compares only the project's own `<artifactId>` (the direct child of `<project>`, namespace-aware), not the ones in `<parent>` or dependencies. Exactly one distinct value -> `true`.
* **Frontend:** a recursive `*.xml` scan under `xml_path`. Every file must parse -> `true`. Reports line and column for bad files.
* **Fails safely:** no POMs, no XML, missing path, path outside the repo, missing or empty `artifactId`, a non-POM root element or an unknown type all give `false` with an actionable message.

### Q4. The decision factor

`passed` -> `result_map["artifact_consistency"]` -> `block_merge = any required entry is not passed` -> the gate step exits 1 -> the job fails -> the build is skipped **and** the required status check blocks the merge.
The artifact check doesn't have its own gate. It joins the existing `result_map` / `block_merge` mechanism, so it's gated exactly like any other check.

---

## Design decisions worth discussing

| Decision | Alternative considered | Why this way |
|---|---|---|
| Action exits 0 and a separate gate step enforces | Action exits non-zero itself | Guarantees `result_map` and `block_merge` are always published (summary, downstream jobs); verdict and enforcement stay separate |
| Gate passes only on the literal `"false"` | `if block_merge == 'true'` -> fail | A missing or empty output (crash, typo) blocks rather than passes |
| `build` has `needs` **and** `if: ... block_merge == 'false'` | `needs` alone | Defence in depth: a future `if: always()` can't let a failed check build |
| `./.github/workflows/pr_check.yml` inside build.yml | Full `owner/repo@ref` | Resolves to the same commit as build.yml, so the version stays consistent automatically |
| Actions referenced as `owner/repo/actions/x@v1` | `./actions/x` | After checkout, `./` means the consumer's files; `uses:` can't be an expression |
| Composite action plus stdlib Python | Docker or JavaScript action | No image pull and no build step; readable; runs anywhere Python runs |
| Inputs passed as env vars | `${{ inputs.x }}` inside `run:` | Prevents script injection from PR-controlled values |
| Registries (`CHECKS`, `VALIDATORS`, `BUILD_PLANS`) | if/else per type | A new type or check is one entry; consumers don't change |
| Static job name `Build` | `Build (${{ inputs.artifact_type }})` | A skipped job's name isn't evaluated; a stable name is needed for required checks. Found while testing on GitHub, fixed in `v1.0.1` |

---

## Known limitations and open points

1. **Maven reactor conflict.** The rule "all artifactIds must match" conflicts with Maven multi-module builds, which need *unique* module artifactIds (confirmed: `mvn validate` on backend-sample reports a duplicate project). It's implemented as specified. The likely real intent should be confirmed; see [assumptions.md](assumptions.md), decision 2.
2. **Mocks.** The build steps print a plan instead of running Maven or npm. The org's other existing PR checks are represented only by the `result_map` input.
3. **Merge enforcement is a repository setting.** Branch protection is configured on the demo repos. In an organization it belongs in an org-level ruleset.
4. **Scale.** A full recursive scan and a JSON output (GitHub caps outputs at 1 MB per job) are fine for normal repos. Very large monorepos would scope the scan with `working_directory` and trim `details`.
5. **Third-party actions** are pinned to major tags (`@v4`, `@v5`). In production, pin them to commit SHAs.

---

## Verification summary

| Level | Result |
|---|---|
| Unit tests | 36 passing (`python -m unittest discover -s tests -v`) |
| Workflow lint | actionlint 1.7.12 clean on all three repos |
| Framework CI on GitHub | Unit tests, 11 PR-check scenarios and 2 build-action runs, all passing |
| End-to-end on GitHub | Backend and frontend on `main` pass. Backend mismatch fails, build skipped, merge blocked. Frontend malformed fails, then passes once fixed |

Full matrix and run links: [test-scenarios.md](test-scenarios.md). Requirement-by-requirement mapping: [requirements-traceability.md](requirements-traceability.md).
