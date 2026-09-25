# devsecops-shared-github-actions

A shared, organization-wide GitHub Actions framework that runs **PR validation before the build** for any repository. It adds an **artifact consistency** check that works for both backend (Maven) and frontend (XML) repositories through **one** consumer workflow.

> **Mock notice.** The organization's real `build.yml`, `pr_check.yml`, `prcheck-utils-action` and build action are private. The versions in this repository are mocks of their *assumed interfaces*, built to show the integration design. Every assumption is listed in [docs/assumptions.md](docs/assumptions.md).

## Repository roles

| Repository | Role |
|---|---|
| `devsecops-shared-github-actions` (this repo) | Owns all shared logic: reusable workflows, the PR-check action, validators, tests |
| `backend-sample` | Demo backend consumer (Maven multi-module). Holds only a thin workflow plus sample data |
| `frontend-sample` | Demo frontend consumer (XML config). Holds only a thin workflow plus sample data |

```
.github/workflows/
  build.yml            reusable: PR Check stage -> gated Build stage     (MOCK)
  pr_check.yml         reusable: checkout -> prcheck-utils-action -> gate (MOCK)
  ci.yml               self-test of this framework (unit tests + action scenarios)
actions/prcheck-utils-action/            the "PR_check action" in image.png
  action.yml           composite action interface                         (MOCK)
  main.py              runs registered checks -> result_map -> block_merge
  utils/
    backend_validator.py   every pom.xml must share one artifactId
    frontend_validator.py  every XML file under xml_path must be well-formed
    result_utils.py        CheckResult, result_map merge, block_merge rule
    fs_utils.py            safe path resolution + deterministic recursive scan
actions/build-action/                    the "build action" in image.png
  action.yml           composite action interface                         (MOCK)
  main.py              resolves and reports the build plan for artifact_type
  utils/build_plans.py artifact_type -> build commands (mvn / npm)
templates/consumer-build.yml  the single consumer workflow to copy
tests/                  unit tests + PASS/FAIL fixtures
docs/                   architecture, assumptions, test scenarios, E2E guide,
                        requirements traceability, reviewer guide
```

## Using it from a consumer repository

Copy [templates/consumer-build.yml](templates/consumer-build.yml) to `.github/workflows/build.yml`. Backend and frontend repositories use the same file. Only the declared configuration changes:

```yaml
# backend repository
jobs:
  build:
    uses: Mahesh2511/devsecops-shared-github-actions/.github/workflows/build.yml@v1
    with:
      artifact_type: backend
```

```yaml
# frontend repository
jobs:
  build:
    uses: Mahesh2511/devsecops-shared-github-actions/.github/workflows/build.yml@v1
    with:
      artifact_type: frontend
      xml_path: config          # any repo-relative directory; nothing is hard-coded
```

| Input | Required | Meaning |
|---|---|---|
| `artifact_type` | yes | `backend` or `frontend`. It's the only source of truth; the type is never inferred from repo name, path or branch |
| `xml_path` | frontend only | Directory, relative to the repo root, that is scanned recursively for `*.xml` |

`Mahesh2511` is the GitHub owner hosting this demo. In a real organization it would be the org, for example `devsecops`.

## How it works

```
consumer build.yml --artifact_type, xml_path--> build.yml
  build.yml   job pr-check --same inputs--> pr_check.yml
                pr_check.yml: [1] checkout consumer source
                              [2] prcheck-utils-action (artifact_type, xml_path)
                                    +- main.py -> backend_validator | frontend_validator
                                    +- result_map["artifact_consistency"] = {passed, ...}
                                    +- block_merge = any required check failed
                              [3] gate: fail the job unless block_merge == "false"
  build.yml   job build   needs: pr-check, if: result == success && block_merge == 'false'
                          checkout -> build-action (artifact_type)
```

* **The PR check always runs before the build.** `build` has `needs: pr-check`, and a failed or blocked PR check skips it.
* **result_map is shared.** `artifact_consistency` is one entry next to any existing checks, such as `security_check`. `block_merge` is computed over *all* required entries, so the artifact check plugs into the existing gate and doesn't add a new one.
* **What actually blocks a merge.** The `block_merge` output on its own blocks nothing. It becomes enforcement when the gate step fails the job. That produces a failed status check, which **branch protection must list as a required status check** (for example `build / PR Check / PR checks`).

Full walkthrough, including the build.yml touchpoints the exercise asks about: [docs/architecture.md](docs/architecture.md).

## Documentation

| Document | Read it when |
|---|---|
| [docs/reviewer-guide.md](docs/reviewer-guide.md) | You're evaluating the exercise (15-minute guided path) |
| [docs/end-to-end-guide.md](docs/end-to-end-guide.md) | You want to follow one PR through every hop, and reproduce it |
| [docs/requirements-traceability.md](docs/requirements-traceability.md) | You want each requirement mapped to code and evidence |
| [docs/architecture.md](docs/architecture.md) | Design reference, extension points, security |
| [docs/assumptions.md](docs/assumptions.md) | Mocked interfaces and interpretation decisions |
| [docs/test-scenarios.md](docs/test-scenarios.md) | PASS/FAIL matrix and GitHub run evidence |

## result_map

```json
{
  "security_check":       { "passed": true },
  "artifact_consistency": {
    "passed": false,
    "required": true,
    "artifact_type": "backend",
    "summary": "Backend artifact consistency FAILED for 3 pom.xml file(s).",
    "errors": ["artifactId mismatch: 2 distinct values found: 'another-service' in service-b/pom.xml; 'sample-service' in pom.xml, service-a/pom.xml"],
    "details": { "files_inspected": ["..."], "artifact_ids": {"...": "..."}, "files_by_artifact_id": {"...": ["..."]} }
  }
}
```

The rule is `block_merge = true` when any entry whose `required` isn't `false` lacks a literal `passed: true`. Malformed entries also block.

## Local development

```bash
# unit tests (stdlib only, Python 3.8+)
python -m unittest discover -s tests -v

# run the action locally against any checkout; --enforce makes the exit code reflect block_merge
python actions/prcheck-utils-action/main.py --artifact-type backend  --workspace ../backend-sample --enforce
python actions/prcheck-utils-action/main.py --artifact-type frontend --xml-path config --workspace ../frontend-sample --enforce
```

`ci.yml` runs the unit tests. It also runs the action itself (`uses: ./actions/prcheck-utils-action`) against every PASS/FAIL fixture and asserts the expected `block_merge`.

## Versioning

Consumers pin to a release tag (`@v1` or `@v1.2.0`), never `@main`. `build.yml` calls `pr_check.yml` with a local `./` reference, which resolves to the same commit as `build.yml`. `pr_check.yml` references the action as `.../prcheck-utils-action@v1`, because `uses:` can't be an expression and a `./` action path would point at the consumer's checkout. A release therefore means moving the major tag after tagging the exact version:

```bash
git tag v1.0.0 && git tag -f v1 && git push origin v1.0.0 && git push -f origin v1
```

A breaking change to inputs or outputs means a new major version (`v2`), and the action reference in `pr_check.yml` is bumped to match.
