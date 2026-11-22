# Radar Dependency Management

> Status: M14-D bootstrap implemented; optional parser extras remain gated by adapter implementation and real-corpus qualification.

## 1. Chosen project model

- pyproject.toml is the canonical project metadata and dependency declaration.
- uv is the selected environment manager and lockfile generator.
- uv.lock is the canonical universal lockfile once optional/runtime dependencies are introduced.
- setuptools is the build backend; its build requirement is pinned in pyproject.toml.
- pip install . remains supported for users who do not want to use uv.
- Do not maintain multiple independently edited dependency lists.

The choice is based on uv's support for PEP 621 project metadata, optional dependency extras, dependency groups, and a universal lockfile across platforms and Python versions. Official documentation:
https://docs.astral.sh/uv/guides/migration/pip-to-project/
https://docs.astral.sh/uv/concepts/projects/dependencies/

## 2. Dependency layers

| Layer | pyproject representation | Install behavior |
|---|---|---|
| Core runtime | project.dependencies | Installed by default; only small, broadly useful dependencies after approval |
| Optional capability | project.optional-dependencies | Installed by named extra, e.g. .[pdf-basic] |
| Development/test | dependency-groups | Local/CI only; never shipped as runtime requirements |
| Build | build-system.requires | Isolated build environment; exact or tightly bounded versions |
| External tool | Not a Python dependency | Installed separately and detected at runtime |

Current pyproject.toml declares no third-party runtime dependencies. The committed uv.lock was generated with uv 0.13.9 and currently locks only the editable Radar project. The first optional extras will be added only when their adapter is implemented and its tests pass. Benchmark-only tools stay in isolated benchmark workflows and do not become application dependencies.

## 3. Version and lock policy

- Pin the build backend and any native or model-heavy dependencies.
- For Core, use a narrow compatible range only when upstream patch releases are safe and the lockfile freezes the resolved version.
- For optional extras, keep version constraints and Python markers explicit.
- Generate and update uv.lock with uv lock; CI must use uv lock --check and uv sync --locked.
- Lock all approved extras so a user can reproduce a PDF or code-analysis environment.
- Store environment exports and benchmark metadata as CI artifacts; do not treat pip freeze output as the canonical project declaration.
- Never update dependencies silently in an unrelated feature commit.

## 4. CI matrix

1. Core compatibility: Python 3.9 and current supported Python; install the project with no extras and run all existing tests.
2. PDF basic: test each approved PDF engine in its own optional-extra job.
3. PDF native: test supported OS/architecture wheels for PDFium if it is adopted.
4. Code syntax: test Tree-sitter extras only on supported Python versions (current tested group requires Python >=3.10).
5. Packaging: build wheel and sdist, install wheel in a clean environment, run radar --help and python -m radar --help.
6. Security: run a Python dependency vulnerability audit on locked environments.
7. License: produce a transitive dependency and bundled-binary license inventory; review model weights and rule datasets separately.

Optional jobs must not make the Core test matrix depend on optional packages.

## 5. Security and license governance

- Review direct and transitive dependencies, not just the top-level package.
- For native wheels, review bundled shared libraries and their licenses.
- For parser packages, test malicious/oversized input, timeouts, and crash isolation.
- Run vulnerability audit on every lockfile change and on a scheduled cadence.
- Record accepted CVEs, temporary exceptions, and remediation deadlines.
- Do not add a dependency with unknown license or unclear model/data redistribution rights.
- ScanCode is a candidate external tool for license inventory, not a runtime dependency.

## 6. Current package bootstrap

The initial pyproject.toml and uv.lock establish:

- package name datongcfl-radar;
- version sourced from radar.__version__;
- Python >=3.9;
- no third-party Core runtime dependencies;
- radar console-script entry point.
- a universal lockfile verified by uv lock --check.
- a Python 3.9 / 3.13 package smoke workflow that runs all 242 tests, both CLI entry points, and builds wheel + sdist.

No PDF or Tree-sitter extras are declared yet because the adapters have not been integrated into Radar's public runtime API. The isolated benchmark jobs pin their own packages independently.

## 7. Change procedure

1. Open a focused dependency/adapter change.
2. Record the gap, alternatives, version/Python compatibility, licenses, transitive tree, and benchmark evidence.
3. Add or update the relevant optional extra in pyproject.toml.
4. Regenerate uv.lock.
5. Add adapter tests and a missing-extra test.
6. Update the CI matrix and license/security reports.
7. Run Core and optional jobs; record exact test counts and package versions.
8. Only then consider promoting a dependency from optional to Core.

## 8. Rollback

- Remove the optional extra and adapter registration without changing Evidence/Pack contracts.
- Keep existing stdlib parser behavior as fallback.
- If a Core dependency must be removed, first provide a compatible fallback and migration path.
- A parser outage must not corrupt Workspace records or change existing Evidence identities.
