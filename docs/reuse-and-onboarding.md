# Reuse and onboarding

This framework is meant to serve every repository in the organization, including ones that don't exist yet. This page explains what makes it reusable, how a new repository adopts it, how the framework itself grows, and where the current limits are.

## 1. What makes it reusable

| Property | How it's achieved | Where |
|---|---|---|
| One contract for every repo | A consumer only sets `artifact_type` (and `xml_path` for frontend). No logic lives in consumer repos | `templates/consumer-build.yml` |
| Nothing repository-specific in shared code | No repo names, artifact IDs, module names, folder names or file counts. A grep audit of `actions/` and the workflows returns nothing | All of `actions/` and `.github/workflows/` |
| Layout independence | Backend scans every `pom.xml` recursively from the repo root, at any depth. Frontend scans whatever directory `xml_path` names | `utils/fs_utils.py` `find_files()` |
| Explicit declaration, not inference | The type is never guessed from the repo name, branch or files present, so an unusual repo layout can't confuse it | `main.py` `run_artifact_consistency()` |
| Safe with any input | Paths are resolved and rejected if they leave the repo. Unknown types, missing paths and empty results all fail with a clear message | `resolve_within()`, validators |
| Plugs into the existing gate | The check is one `result_map` entry, and `block_merge` is computed over all entries, so other checks and future checks share one gate | `utils/result_utils.py` |
| Extensible by registration | New artifact type: one entry in `VALIDATORS` and `BUILD_PLANS`. New check: one entry in `CHECKS`. No consumer changes | `main.py`, `build-action/utils/build_plans.py` |
| Versioned | Consumers pin `@v1`. Compatible changes move `v1`; breaking changes ship as `v2` | Release tags |
| Self-tested | CI runs the unit tests and the real actions against PASS/FAIL fixtures before every release | `.github/workflows/ci.yml` |

The two sample repositories prove this. They have different layouts, different types and different settings, and they use the same shared code without any special cases.

A third repository, [payments-service](https://github.com/Mahesh2511/payments-service), was onboarded later by copying only the template. It has a different artifactId (`payments`) and a nested module at `api/v2/core/`, and it passed on its first run ([run 36120406422](https://github.com/Mahesh2511/payments-service/actions/runs/36120406422)) with no change to the framework.

## 2. Onboarding a new repository

A new repository needs one file and one setting.

**Step 1.** Copy `templates/consumer-build.yml` to `.github/workflows/build.yml` in the new repo and set the declaration:

```yaml
jobs:
  build:
    uses: Mahesh2511/devsecops-shared-github-actions/.github/workflows/build.yml@v1
    with:
      artifact_type: backend            # or: frontend
      # xml_path: src/main/resources    # frontend only, any repo-relative directory
```

**Step 2.** Open a PR (or use *Actions > Build > Run workflow*) and confirm that both `build / PR Check / PR checks` and `build / Build` pass.

**Step 3.** Protect `main`. Under *Settings > Branches* (or *Rules*), require the status check `build / PR Check / PR checks`. In an organization, do this once in an org-level ruleset instead of per repo.

That's all. No code is copied, and the repo automatically gets future framework fixes through `@v1`.

**Private or internal shared repo.** If the shared repository isn't public, set *Settings > Actions > General > Access* on it so the organization's repositories can use its workflows and actions.

**Monorepo.** The action already accepts `working_directory`, which moves the scan root into a subfolder. To offer this to consumers, add `working_directory` as an optional input to `build.yml` and `pr_check.yml` and pass it through, the same way as `xml_path`. It's a compatible change (a minor release).

## 3. Growing the framework

| Change | Steps | Release |
|---|---|---|
| New artifact type (e.g. `node`) | Add `utils/node_validator.py` and register it in `VALIDATORS`. Add a `node` entry to `BUILD_PLANS`. Add fixtures, tests and CI scenarios | Minor (`v1.2.0`), and move `v1` |
| New PR check (e.g. license headers) | Write a function that returns `CheckResult` and register it in `CHECKS`. It becomes a new `result_map` key and takes part in `block_merge` automatically | Minor |
| Roll out a check gradually | Return `CheckResult(..., required=False)` first. It's reported in the job summary but never blocks. Switch to `required=True` when false positives are fixed | Minor, then minor |
| New optional setting | Add an input with a default to `build.yml`, `pr_check.yml` and `action.yml`. Existing consumers keep working | Minor |
| Rename or remove an input, change output format | Breaking | Major (`v2`); consumers opt in by changing `@v1` to `@v2` |

Release steps:

```bash
git tag v1.2.0 && git tag -f v1
git push origin v1.2.0 && git push -f origin v1
```

## 4. Moving to another organization

The owner and repository name appear in exactly three places, because a `uses:` value can't be an expression:

| File | Line |
|---|---|
| `.github/workflows/pr_check.yml` | `uses: <owner>/devsecops-shared-github-actions/actions/prcheck-utils-action@v1` |
| `.github/workflows/build.yml` | `uses: <owner>/devsecops-shared-github-actions/actions/build-action@v1` |
| `templates/consumer-build.yml` | `uses: <owner>/devsecops-shared-github-actions/.github/workflows/build.yml@v1` |

Replace the owner in all three, push, and tag `v1`. Nothing else refers to the owner.

## 5. Known limits and how to address them

| Limit | Impact | Remedy |
|---|---|---|
| Inner action references float on `@v1` | A consumer pinned to `build.yml@v1.0.0` still runs the *current* `v1` actions, because `pr_check.yml` and `build.yml` reference them as `@v1` | Only matters for consumers pinned to an exact version. To make an exact tag fully immutable, the release process would rewrite the inner references to the exact version before tagging |
| Runner label is `ubuntu-latest` | Orgs using self-hosted runners need a different label | Add an optional `runs_on` input with default `ubuntu-latest` (minor release) |
| Job outputs are capped at 1 MB | A huge repository with thousands of failures could exceed it | Trim `details` to counts plus the first N errors; the full report goes to the job summary or an uploaded artifact |
| Consumers can edit their own workflow in a PR | A PR could change `artifact_type` or remove the call | The required check must still appear and pass, and code review sees the workflow change. The org-level fix is a ruleset with required workflows, which run from the central repo |
| Build steps are mocked | `build-action` prints the plan instead of running Maven or npm | Replace the plan printing with real commands once the Maven artifactId question is settled (see assumptions.md, decision 2) |
