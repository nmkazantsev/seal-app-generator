# Seal Engine updater modules and main flow

## Goal

Keep the app generator easy to find and maintain while making engine updates work with generated workspaces and consumer projects that use different layouts. Keep the update flow visible in one small `main.py` file. Prefer direct functions and straightforward data flow over frameworks or generic abstractions.

## User-facing behavior

- `generate_seal_app.py` remains the separate app generator and its behavior stays unchanged.
- `main.py` becomes the readable orchestration entry point for updating the engine: parse options, resolve and confirm the project root when omitted, run the updater, and report the result.
- `update_engine.py` remains a compatibility launcher so existing commands continue to work, and re-exports `update_workspace_engine` because `generate_seal_app.py` imports that function.
- With no project path, prompt in the terminal to use the current working directory. Require an explicit path when stdin is non-interactive. A declined confirmation cancels without downloading or writing files.
- Find engine libraries by reading literal local artifact paths in Gradle files and by checking known engine artifact names in `libs/` folders. Ignore VCS and generated build directories. A selected parent directory may include both desktop and mobile projects.
- Require release assets only for artifact types found in the selected tree. Update every discovered copy of those artifacts. Treat `obj-0.4.0.jar` as optional when the release omits it.
- If a project uses `android.aar` but the release provides only `android.jar`, replace the existing AAR's `classes.jar` and preserve its manifest and other packaged resources.
- For consumer projects, update existing engine-specific docs while preserving app `README.md` and `PROJECT_MAP_FOR_CODEX.md`. Keep generated-workspace documentation behavior as it is today.
- Keep app generation out of the updater flow; do not change `generate_seal_app.py`.

## Module layout

- `main.py`: explicit updater workflow and user-facing messages.
- `update_engine.py`: backward-compatible launcher into `main.py` and re-export of `update_workspace_engine` for the app generator.
- `seal_engine_updater/cli.py`: argument parsing and current-directory confirmation.
- `seal_engine_updater/discovery.py`: root validation, library discovery, and safe engine-doc discovery.
- `seal_engine_updater/github.py`: GitHub release lookup, downloads, asset matching, and release-doc extraction.
- `seal_engine_updater/updater.py`: coordinate discovery, fetch only needed assets, copy binaries, and write docs.
- `seal_engine_updater/errors.py`: shared updater error type.
- `generate_seal_app.py`: remains the independent app-generation script.

The dependency flow is one-way: `main.py` calls the CLI helpers and updater; the updater calls discovery and GitHub helpers. Discovery and GitHub access do not import each other. The package modules expose focused functions, and the main flow remains readable without needing to inspect implementation details first.

## Safety and error handling

- Resolve the selected project root before network access.
- If no known engine library is found, report the selected root and ask for a more suitable project path.
- Do not write outside the selected root when resolving Gradle paths.
- Do not replace consumer-owned README or project-map files.
- Preserve the current exit behavior for update failures and keyboard interruption where practical.

## Version control and verification

- Commit this design separately before implementation.
- Keep the behavior change and module extraction in reviewable commits.
- Do not add or run tests unless requested. Perform a syntax check and inspect the final diff before reporting completion.

## Out of scope

- Changing app creation behavior or generated templates.
- Updating consumer project files while developing this tool.
- Supporting Gradle expressions that require evaluating Gradle itself; discovery handles literal local file paths and conventional `libs/` directories.
