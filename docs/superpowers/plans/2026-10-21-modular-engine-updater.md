# Modular Engine Updater Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the engine updater into small, readable files while keeping app generation separate, supporting varied Gradle layouts, and verifying the updater against desktop and mobile Tanki projects on dedicated branches.

**Architecture:** `main.py` shows the update flow and delegates argument handling to a small package. `seal_engine_updater/` separates discovery, GitHub access, updating, and shared errors. `generate_seal_app.py` remains unchanged, and `update_engine.py` remains a compatibility launcher and keeps the function imported by the generator.

**Tech Stack:** Python 3.10+, standard library, `unittest`, Gradle wrapper.

**Spec:** `docs/superpowers/specs/2026-10-21-updater-modules-design.md`

## Global Constraints

- Keep the app generator separate and do not change app creation behavior.
- Keep `python3 update_engine.py [PROJECT_ROOT]` working.
- When no project path is provided, confirm the current directory interactively; require an explicit path without an interactive terminal.
- Discover literal engine library paths from Gradle and known artifact names in `libs/` folders; skip VCS and generated build directories.
- Never write outside the selected project root.
- In consumer projects, update existing engine-specific docs and preserve app `README.md` and `PROJECT_MAP_FOR_CODEX.md`.
- Do not add dependencies or complex/general-purpose abstractions.

## Review Focus

- A Gradle dependency points outside the selected root: it must not write outside that root. Cover with a discovery unit test.
- The root contains desktop and mobile subprojects with different `libs/` paths: discover both. Cover with a discovery unit test.
- The user omits a path in a terminal: confirm before update. Cover yes/no input using `unittest.mock`.
- The user omits a path in a non-interactive run: stop before network access. Cover stdin without a TTY.
- The selected root is not a generated workspace: preserve its app README and project map. Cover with an updater doc-target unit test.
- A release provides `android.jar` for an existing `android.aar`: update classes and preserve packaged resources. Cover with an updater unit test.

---

### Task 1: Characterize project discovery and CLI behavior

**Files:**
- Create: `tests/test_update_engine.py`
- Modify: none

**Interfaces:**
- Consumes: current `update_engine._discover_engine_targets(project_root)` and current CLI entry behavior.
- Produces: test cases that pin path discovery, root containment, and no-path confirmation before module extraction.

- [x] **Step 1: Write unittest cases** for Gradle literal paths across nested desktop/mobile folders, conventional `libs/` fallback, excluded `.git`/`build` paths, outside-root references, yes/no prompt, and non-interactive omitted path.
- [x] **Step 2: Run `python3 -m unittest discover -s tests -v`**; expected output is all new tests passing against the current updater implementation. Resolve any mismatch before refactoring.
- [x] **Step 3: Commit** as `test: characterize engine updater discovery`.

### Task 2: Split updater responsibilities into modules

**Files:**
- Create: `main.py`
- Create: `seal_engine_updater/__init__.py`
- Create: `seal_engine_updater/errors.py`
- Create: `seal_engine_updater/cli.py`
- Create: `seal_engine_updater/discovery.py`
- Create: `seal_engine_updater/github.py`
- Create: `seal_engine_updater/updater.py`
- Modify: `update_engine.py`
- Modify: `tests/test_update_engine.py`
- Modify: `README.md`
- Modify: `structure.md`

**Interfaces:**
- `seal_engine_updater.errors.UpdateEngineError(RuntimeError)` is shared by modules.
- `seal_engine_updater.cli.parse_args(argv: list[str]) -> argparse.Namespace` parses updater options.
- `seal_engine_updater.cli.resolve_cli_project_root(path: str | None, *, stdin_isatty: bool, input_fn=input, cwd: Path | None = None) -> Path | None` returns the selected root or `None` when declined.
- `seal_engine_updater.discovery.discover_engine_targets(root: Path) -> dict[str, set[Path]]` returns existing paths keyed by canonical artifact filename.
- `seal_engine_updater.discovery.discover_engine_docs(root: Path) -> dict[str, set[Path]]` returns existing engine-specific documentation paths.
- `seal_engine_updater.github.get_latest_release(repo: str, token: str | None) -> tuple[dict, dict[str, str]]` returns release metadata and required engine docs.
- `seal_engine_updater.updater.update_project_engine(root: Path, *, repo: str, token: str | None, verbose: bool) -> str` updates discovered artifacts/docs and returns the tag.
- `main.main(argv: list[str] | None = None) -> int` coordinates parse, root selection, update, and exit messages.
- `update_engine.py` delegates CLI execution to `main.main`, re-exports `update_workspace_engine` for the generator, and retains the existing script invocation.

- [x] **Step 1: Move root validation and library/doc scanning** into `discovery.py`; update tests to import that public function.
- [x] **Step 2: Move HTTP, release matching, downloads, and zip documentation extraction** into `github.py`; retain the same timeout and GitHub error reporting behavior.
- [x] **Step 3: Move orchestration and file writes** into `updater.py`; preserve conditional release asset selection and generated-workspace documentation behavior.
- [x] **Step 4: Add `cli.py`, `main.py`, package files, and the compatibility launcher** with direct, readable control flow.
- [x] **Step 5: Run `python3 -m unittest discover -s tests -v`**; expected output is all characterization tests passing.
- [x] **Step 6: Run `python3 -m compileall -q main.py update_engine.py seal_engine_updater tests`**; expected exit code is 0.
- [x] **Step 7: Update usage/structure docs and inspect the complete diff**, confirming `generate_seal_app.py` is unchanged.
- [ ] **Step 8: Commit** as `refactor: split engine updater into modules`.

### Task 3: Verify desktop and mobile Tanki projects on separate branches

**Files:**
- Modify only inside the Tanki repositories using the updater: recognized engine libraries and existing engine-specific docs.
- Do not stage or commit any pre-existing edits in the mobile repository.

**Interfaces:**
- Consumes: `python3 update_engine.py PROJECT_ROOT` and the release published by `nmkazantsev/Seal-Engine-3M`.
- Produces: one dedicated branch per Tanki repository with only the engine update committed.

- [ ] **Step 1: Create a branch** named `codex/engine-update-desktop` in `../Tanki7-1` and `codex/engine-update-mobile` in `../Tanki7-1-mobile`; leave all existing staged and unstaged mobile edits untouched.
- [ ] **Step 2: Run `python3 update_engine.py ../Tanki7-1`** from this repository; expected output lists and updates discovered desktop artifacts/docs, including the release `android.jar` found in `libs/`.
- [ ] **Step 3: Run `python3 update_engine.py ../Tanki7-1-mobile`**; expected output updates mobile artifacts/docs and adapts the release `android.jar` into the existing `android.aar` while preserving AAR resources. The desktop branch already supplies the shared `core.jar` dependency.
- [ ] **Step 4: Build desktop with `./gradlew build`** from `../Tanki7-1`; expected exit code is 0.
- [ ] **Step 5: Build mobile with `./gradlew assembleDebug`** from `../Tanki7-1-mobile`; expected exit code is 0.
- [ ] **Step 6: Stage only engine binaries and engine-specific docs changed by the updater**, verify the staged file list excludes pre-existing mobile edits, and commit each Tanki branch as `chore: update Seal Engine`.
- [ ] **Step 7: Report branch names, engine tag, build results, and any files intentionally left untouched.**
