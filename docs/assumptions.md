# Assumptions and mocked interfaces

The exercise references `devsecops/shared-github-actions/.github/workflows/build.yml`, `pr_check.yml` and `prcheck-utils-action`. These belong to a private internal framework and weren't provided. As the clarification from the reviewers asked, this repository contains **mock implementations of assumed interfaces**. This file documents every assumption so it can be reconciled with the real framework.

## Assumed interfaces

### `build.yml` (reusable workflow, `on: workflow_call`)

| Direction | Name | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| input | `artifact_type` | string | yes | | `backend` \| `frontend` |
| input | `xml_path` | string | no | `""` | Required by the frontend rules |
| output | `result_map` | string (JSON) | | | Forwarded from pr_check.yml |
| output | `block_merge` | string | | | `"true"` \| `"false"` |

Jobs: `pr-check` (calls `pr_check.yml`), then `build` (`needs: pr-check`).
**Assumed about the real one:** it already has a PR-check stage that runs before the build, and adding inputs to it is acceptable. Its build job delegates to `build-action`, whose real toolchain steps (Maven, npm, publishing) are mocked.

### `pr_check.yml` (reusable workflow, `on: workflow_call`)

| Direction | Name | Type | Required | Default |
|---|---|---|---|---|
| input | `artifact_type` | string | yes | |
| input | `xml_path` | string | no | `""` |
| output | `result_map` | string (JSON) | | |
| output | `block_merge` | string | | |

Steps: checkout → prcheck-utils-action → gate step that fails the job unless `block_merge == "false"`.
**Assumed about the real one:** it already runs other checks through prcheck-utils-action and enforces `block_merge` by failing the job. If the real workflow enforces differently, for example through a separate gating job, the artifact check still plugs in unchanged, because it only contributes a `result_map` entry.

### `prcheck-utils-action` (composite action)

| Direction | Name | Required | Default | Notes |
|---|---|---|---|---|
| input | `artifact_type` | yes | | Selects the artifact_consistency validator |
| input | `xml_path` | no | `""` | Frontend scan directory |
| input | `result_map` | no | `"{}"` | result_map from earlier checks; the new entry is merged in |
| input | `working_directory` | no | `"."` | Scan root inside the workspace (for monorepos and the framework's own CI) |
| output | `result_map` | | | JSON object keyed by check name |
| output | `block_merge` | | | `"true"` \| `"false"` |

**Assumed about the real one:** it runs a set of checks, records each in a map keyed by check name with a boolean pass flag, and derives `block_merge` as "any required check failed". The mock's check registry (`CHECKS` in `main.py`) stands in for those existing checks. Only `artifact_consistency` is implemented, because the exercise says not to add unrelated validators.

### `build-action` (composite action)

| Direction | Name | Required | Notes |
|---|---|---|---|
| input | `artifact_type` | yes | Selects the build plan (`utils/build_plans.py`) |
| output | `artifact_type` | | Normalized type that was built |
| output | `build_status` | | `mocked` |

**Assumed about the real one:** the diagram (`image.png`) shows a build action next to the PR-check action with the same `action.yml` / `utils` / `main.py` layout. The mock resolves the per-type plan (`mvn -B -ntp verify` for backend; `npm ci`, `npm run build` for frontend) and prints it without running it. Running it would fail on purpose for backend-sample (see interpretation decision 2), and the frontend sample has no `package.json`. An unknown type fails the build step.

### `result_map` entry schema (assumed)

```json
{ "<check>": { "passed": true, "required": true, "summary": "...", "errors": [], "details": {} } }
```

Only `passed` is load-bearing for gating. `required` defaults to `true`. The other fields are diagnostics.

## Mocked or simplified GitHub Actions behaviour

| Area | In this repo | Real organization |
|---|---|---|
| Owner and repo | `Mahesh2511/devsecops-shared-github-actions` (personal account standing in for the org) | e.g. `devsecops/shared-github-actions` |
| Version | `@v1` major tag | The org's release tags |
| Build steps | `build-action` prints the per-type plan | Real toolchain steps |
| Merge blocking | Failed `PR checks` job; required status check configured manually | Org ruleset requiring the PR-check status on all repos |
| Existing PR checks | Not implemented; `result_map` input accepts their results | security, dependency and other checks |
| Cross-repo access | Shared repo must be public, or (if private or internal) *Settings → Actions → General → Access* must allow other repos in the org/account | Same |

## Interpretation decisions

1. **"artifactId of each pom.xml"** means the project's own coordinate: the `<artifactId>` that is a direct child of `<project>`. Values inside `<parent>`, `<dependencies>`, `<plugins>` and so on are ignored. Otherwise every POM with a dependency would "mismatch".
2. **Maven reactor caveat.** In a real multi-module Maven build, every module must have a *unique* `groupId:artifactId`. A reactor where all modules share one `artifactId` fails with `Project '…' is duplicated in the reactor`. Verified with Maven 3.9.16 on `backend-sample`: `Project 'com.example:sample-service:1.0.0-SNAPSHOT' is duplicated in the reactor`. The demo is unaffected because the build step is mocked. The rule is implemented exactly as specified ("all artifactId values must match"), and the sample project follows it. Likely intents in the real organization are repositories that contain several single-module POMs for one artifact, or a rule that really means "all modules share the same parent artifactId". Either is a small change in `backend_validator.extract_artifact_id`, and this should be confirmed with the framework owners.
3. **"All" `pom.xml` means recursive from the repository root.** Only `.git/` is skipped. Build output (`target/`) isn't present on a fresh checkout, so no other exclusions are hard-coded.
4. **No files found is a failure.** A backend repo without `pom.xml`, or an `xml_path` with no `*.xml`, is treated as misconfiguration, not as a vacuous pass.
5. **Frontend "valid" means well-formed.** No XSD or DTD validation and no content comparison. The extension match is case-insensitive (`.xml`, `.XML`).
6. **`artifact_type` is validated in the action**, because `workflow_call` string inputs can't declare allowed values. It's case- and whitespace-insensitive (`" Backend "` → `backend`).
7. **The action exits 0 when it produces a verdict.** Enforcement lives in `pr_check.yml`'s gate step, so `result_map` and `block_merge` are always published. `main.py --enforce` exists for local or standalone use.
8. **Consumer triggers:** `pull_request` as required, plus `workflow_dispatch` for manual demo runs.
