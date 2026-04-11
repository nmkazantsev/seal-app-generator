# Seal App Generator

This tool generates one Seal Engine workspace with separate application folders:

- `<project_name>/desktop`: desktop Gradle project using `libs/core.jar` and `libs/desktop.jar`
- `<project_name>/android`: Android Gradle project using `app/libs/android.aar` and the desktop project's shared `game` module

By default the workspace is created under `/home/nikita/IdeaProjects/`.

The generated workspace follows this structure:

- shared gameplay code lives in `desktop/game`
- the Android app references `../desktop/game`
- the workspace root gets a short generated `README.md` plus copied engine docs
- both app roots still receive `PROJECT_MAP_FOR_CODEX.md`, `README.md`, and `ENGINE-README.md`
- required wrappers, icons, engine binaries, and docs come from `template_src/` when present, otherwise from `template_payload.zip`

## Usage

```bash
python3 tools/seal_app_generator/generate_seal_app.py MyGame
```

Optional arguments:

```bash
python3 tools/seal_app_generator/generate_seal_app.py MyGame \
  --output-dir /home/nikita/IdeaProjects \
  --desktop-package com.example.mygame.desktop \
  --game-package com.example.mygame.game \
  --android-package com.example.mygame.mobile \
  --android-name "MyGame Android" \
  --force
```

## Output

Workspace root:

- `README.md` with the generated layout and build commands
- `PROJECT_MAP_FOR_CODEX.md` and `ENGINE-README.md`

Desktop app:

- `build.gradle`, `settings.gradle`, Gradle wrapper
- `libs/core.jar`, `libs/desktop.jar`, `libs/obj-0.4.0.jar`
- launcher `Main.java`
- shared `game` module with a starter `MainRenderer` that draws a Hello World window

Android app:

- `build.gradle`, `settings.gradle`, `gradle.properties`, Gradle wrapper
- `app/libs/core.jar`, `app/libs/android.aar`, `app/libs/obj-0.4.0.jar`
- `MainActivity.java`
- copied Android resources and launcher icons
- source set wiring to `../desktop` resource folders

## Notes

The generator intentionally uses local binary engine dependencies, not engine source modules.
