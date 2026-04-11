# Tool Structure

This document describes the editable resources used by `seal_app_generator`.

## Main Entry Point

- `generate_seal_app.py`
  The generator script.
  Contains:
  - CLI arguments and help text
  - all generated text templates for Gradle files, Java files, Android resources, and the workspace README
  - filesystem logic that creates the output workspace
  - payload loading logic

## Editable Template Sources

- `template_src/`
  Preferred source for generated static files.
  If this directory exists, the generator uses it directly.
  This is the best place to edit bundled resources during development.

- `template_src/desktop/`
  Static files copied into every generated `desktop/` project.
  Currently this is mostly the Gradle wrapper.

- `template_src/android/`
  Static files copied into every generated `android/` project.
  Contains:
  - Gradle wrapper
  - default Android resources
  - template test source folders

- `template_src/shared/libs/desktop/`
  Local binary dependencies copied into generated `desktop/libs/`.
  Current contents:
  - `core.jar`
  - `desktop.jar`
  - `obj-0.4.0.jar`

- `template_src/shared/libs/android/`
  Local binary dependencies copied into generated `android/app/libs/`.
  Current contents:
  - `core.jar`
  - `android.aar`
  - `obj-0.4.0.jar`

- `template_src/shared/docs/`
  Engine-facing docs copied into generated projects.
  Contains:
  - `README.md`
  - `PROJECT_MAP_FOR_CODEX.md`

## Payload Archive

- `template_payload.zip`
  Fallback bundle used only when `template_src/` is missing.
  It should contain the same `template_src/` tree.
  If you edit files in `template_src/`, regenerate this archive only if you need the standalone packed fallback to stay in sync.

## Repo Docs

- `README.md`
  User-facing description of the tool, output layout, and CLI usage.

- `REMARKS.md`
  Short implementation notes and behavior summary.

- `structure.md`
  This file.

## How Generation Is Split

In `generate_seal_app.py`, the important functions are:

- `parse_args()`
  CLI options and defaults.

- `extract_payload()`
  Chooses `template_src/` or falls back to `template_payload.zip`.

- `create_workspace_docs(...)`
  Writes the generated workspace-level `README.md` and root docs.

- `create_desktop_project(...)`
  Creates `desktop/`, copies desktop libs/docs, and writes desktop/game sources.

- `create_android_project(...)`
  Creates `android/`, copies Android libs/docs/resources, and writes Android Gradle and Java files.

- `main()`
  Builds the context and orchestrates workspace generation.

## Where To Edit Common Things

- Change default output path:
  Edit `parse_args()` in `generate_seal_app.py`.

- Change generated `MainRenderer` or launcher code:
  Edit `GAME_RENDERER_TEMPLATE` or `DESKTOP_MAIN_TEMPLATE` in `generate_seal_app.py`.

- Change generated Android Gradle wiring:
  Edit `ANDROID_SETTINGS_TEMPLATE` and `ANDROID_APP_BUILD_TEMPLATE` in `generate_seal_app.py`.

- Change bundled Gradle wrappers or Android resources:
  Edit files under `template_src/desktop/` or `template_src/android/`.

- Change bundled engine docs copied into generated projects:
  Edit files under `template_src/shared/docs/`.

- Change bundled local engine binaries:
  Replace files in `template_src/shared/libs/desktop/` or `template_src/shared/libs/android/`.
