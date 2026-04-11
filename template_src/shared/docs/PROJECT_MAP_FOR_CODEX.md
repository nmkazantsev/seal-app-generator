# PROJECT_MAP_FOR_CODEX (Application-Focused)

This project map is optimized for an application/game that uses Seal Engine 3-M as a compiled dependency (`JAR`/`AAR`), where engine source code is usually not part of the application repository.

If you are changing the engine itself (this repository), open `ENGINE_INTERNALS_MAP_FOR_CODEX.md` instead.

## 1. Recommended Reading Order

1. `README.md` (public API overview; contains a user-oriented manual for engine v3.2.1).
2. This file: `PROJECT_MAP_FOR_CODEX.md` (how apps integrate the engine).
3. A real consumer project (pick the closest to your target):
   - Desktop demo launcher (engine sources included as Gradle modules): `~/IdeaProjects/Seal_Engine_3-M/Demo`
   - Android demo app (engine sources included as Gradle modules): `~/IdeaProjects/Seal_Engine_3-M/Demo-app`
   - Desktop application consuming engine as local JARs: `~/IdeaProjects/Seal_Engine_3-M/Tanki-7.1`
4. Only if required: `ENGINE_INTERNALS_MAP_FOR_CODEX.md` (engine internals/source-level map).

## 2. App-Side Mental Model

- Your game/app is structured as “pages” (screens) implemented as `GamePageClass`.
- A platform-specific launcher creates an `Engine` and starts the first page.
- Pages tend to own resources (textures, shaders, framebuffers, touch processors). Many engine objects accept a `GamePageClass creator` parameter for ownership/lifecycle.
- Navigation is explicit: `engine.startNewPage(newPage)`. Treat page transitions as a hard resource boundary.

## 3. How Consumers Depend On The Engine (Observed Patterns)

### 3.1 Engine as local JARs (desktop)

Observed in `~/IdeaProjects/Seal_Engine_3-M/Tanki-7.1/build.gradle`:

```gradle
implementation files("libs/core.jar", "libs/desktop.jar")
```

This is the default assumption for application work in Codex: you can use engine APIs, but you should not rely on reading/modifying engine source.

### 3.2 Engine as included Gradle modules (engine-dev convenience)

Observed in the demo projects (`~/IdeaProjects/Seal_Engine_3-M/Demo`, `~/IdeaProjects/Seal_Engine_3-M/Demo-app`): they include engine modules via `settings.gradle` `projectDir` pointing to `../sealEngine_3M/*`.

This is convenient when iterating on engine + app together, but it should not be assumed in general application repositories.

## 4. Bootstrap Patterns (Desktop vs Android)

### 4.1 Desktop bootstrap (observed)

Observed in `~/IdeaProjects/Seal_Engine_3-M/Demo/src/main/java/com/nikitos/Main.java` and `~/IdeaProjects/Seal_Engine_3-M/Tanki-7.1/src/main/java/com/nikitos/Main.java`:

- Create `LauncherParams` and configure:
  - `setFullScreen(boolean)`
  - `setDebug(boolean)`
  - `setStartPage(unused -> new YourStartPage())`
- Create `DesktopLauncher(launcherParams)` and call `run()`.

### 4.2 Android bootstrap (observed)

Observed in `~/IdeaProjects/Seal_Engine_3-M/Demo-app/app/src/main/java/com/example/androiddemo/MainActivity.java`:

- In `Activity.onCreate(...)`:
  - create `AndroidLauncherParams(context)` and configure:
    - `setDebug(boolean)`
    - `setStartPage(unused -> new YourStartPage())`
    - `setMSAA(boolean)`
  - create `AndroidLauncher(androidLauncherParams)`
  - keep the `Engine`: `engine = androidLauncher.getEngine()`
  - set content view to the returned `GLSurfaceView`: `setContentView(androidLauncher.launch())`
  - forward touch events into the engine input system:
    - `TouchProcessor.onTouch(new AndroidMotionEventAdapter(event))`
- In `Activity.onPause()` / `Activity.onResume()` call `engine.onPause()` / `engine.onResume()`.

## 5. “Shared Game Module” Pattern (Recommended for real apps)

The demos show a high-leverage pattern for cross-platform code reuse:

- Put gameplay/pages in a separate module (often called `game`).
- Desktop and Android “host” projects depend on `game` and only decide which start page to run.
- In generator-created workspaces, this shared module is located at `desktop/game`, and the Android project includes it through `../desktop/game`.

Observed examples:

- `~/IdeaProjects/Seal_Engine_3-M/Demo/game/src/main/java/com/nikitos/MainRenderer.java` is a `GamePageClass` used as the start page on both desktop and Android demos.
- `~/IdeaProjects/Seal_Engine_3-M/Tanki-7.1/game/src/main/java/tanki7/main/renderers/MainRenderer.java` is a thin `GamePageClass` delegating work to game-level objects.

## 6. App-Side Work: What To Inspect First

When asked to modify an application built on Seal Engine, start in this order:

1. The app’s dependency wiring:
   - Does it use `implementation files(...)` (local JARs) or included Gradle modules?
2. The platform bootstrap:
   - Desktop: `main(...)` that builds `LauncherParams` and runs `DesktopLauncher`
   - Android: `Activity` that builds `AndroidLauncherParams`, calls `launch()`, forwards touch, and forwards pause/resume
3. The start page and page graph:
   - Find the `setStartPage(...)` lambda
   - Search for `startNewPage(...)` to locate navigation
4. The page that owns the feature:
   - rendering code tends to live in `GamePageClass.draw()`
   - resize-dependent initialization tends to live in `onSurfaceChanged(...)`
5. Assets in the *application* repo:
   - shaders, textures, models, fonts, audio, config

## 7. Common App-Level Tasks (Where To Change Code)

### 7.1 New screen / menu / mode

- Implement a new `GamePageClass`.
- Switch to it via `engine.startNewPage(new YourPage())`.
- Ensure the new page creates heavy assets once (constructor) and recreates size-dependent resources in `onSurfaceChanged(...)`.

### 7.2 Touch issues

- Android first: verify `MotionEvent` is forwarded to `TouchProcessor` using the platform adapter (see Demo-app).
- Game logic next: find where `TouchProcessor` instances are registered and validate their hitbox logic and coordinate assumptions.

### 7.3 Rendering / shader / asset load failures

- Start from the page code that references the asset path string.
- Verify the asset is packaged where the platform asset manager expects it (Android assets vs desktop classpath resources).
- Only after that, consult engine internals.

## 8. What Not To Do By Default (Application Work)

- Do not start by reading/changing engine source code to implement routine app features.
- Do not assume engine internals are accessible (or changeable) when the engine is a compiled dependency.
- Prefer changes in app code, app assets, and app configuration first.

## 9. When To Use `ENGINE_INTERNALS_MAP_FOR_CODEX.md`

Open the engine internals map only when:

- you are explicitly tasked with changing Seal Engine 3-M itself, or
- an issue cannot be resolved through public API usage (e.g., platform adapter bug, GPU resource lifecycle bug, shader binding bug), and you must trace engine implementation.
- if you need API descriptions, start with `README.md`; only move to the internals map if something is still unclear.
