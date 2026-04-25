#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PAYLOAD_ARCHIVE = SCRIPT_DIR / "template_payload.zip"
PAYLOAD_SOURCE_DIR = SCRIPT_DIR / "template_src"

DESKTOP_SETTINGS_TEMPLATE = """\
pluginManagement {{
    repositories {{
        gradlePluginPortal()
        google()
        mavenCentral()
    }}
}}
dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}
rootProject.name = '{desktop_project_name}'

include 'game'
"""

DESKTOP_BUILD_TEMPLATE = """\
plugins {{
    id 'java'
    id 'com.github.johnrengelman.shadow' version '8.1.1'
}}

group = '{desktop_group}'
version = '1.0-SNAPSHOT'

ext {{
    switch (org.gradle.internal.os.OperatingSystem.current()) {{
        case org.gradle.internal.os.OperatingSystem.WINDOWS:
            lwjglNatives = "natives-windows"
            break
        case org.gradle.internal.os.OperatingSystem.LINUX:
            lwjglNatives = "natives-linux"
            break
        case org.gradle.internal.os.OperatingSystem.MAC_OS:
            lwjglNatives = "natives-macos"
            break
    }}
}}

ext.lwjglVersion = "3.3.3"

dependencies {{
    implementation files(
            "libs/core.jar",
            "libs/desktop.jar"
    )
    implementation files('libs/obj-0.4.0.jar')
    implementation project(':game')

    testImplementation platform('org.junit:junit-bom:5.10.0')
    testImplementation 'org.junit.jupiter:junit-jupiter'
    testRuntimeOnly 'org.junit.platform:junit-platform-launcher'

    implementation 'org.slf4j:slf4j-nop:2.0.17'
    implementation 'com.googlecode.soundlibs:basicplayer:3.0.0.0'
    implementation 'com.googlecode.soundlibs:jlayer:1.0.1.4'
    implementation 'com.googlecode.soundlibs:mp3spi:1.9.5.3'

    implementation 'org.joml:joml:1.10.8'
    implementation "org.lwjgl:lwjgl:${{lwjglVersion}}"

    def skijaVersion = "0.143.10"

    implementation "io.github.humbleui:skija-shared:$skijaVersion"
    implementation "io.github.humbleui:skija-windows-x64:$skijaVersion"
    implementation "io.github.humbleui:skija-linux-x64:$skijaVersion"
    implementation "io.github.humbleui:skija-linux-arm64:$skijaVersion"
    implementation "io.github.humbleui:skija-macos-arm64:$skijaVersion"
    implementation "io.github.humbleui:skija-macos-x64:$skijaVersion"

    implementation "org.lwjgl:lwjgl-glfw:${{lwjglVersion}}"
    implementation "org.lwjgl:lwjgl-opengl:${{lwjglVersion}}"
    implementation "org.lwjgl:lwjgl-opengles:${{lwjglVersion}}"
    implementation(platform("org.lwjgl:lwjgl-bom:$lwjglVersion"))
    implementation "org.lwjgl:lwjgl-stb"

    runtimeOnly "org.lwjgl:lwjgl::$lwjglNatives"
    runtimeOnly "org.lwjgl:lwjgl-opengl::$lwjglNatives"
    runtimeOnly "org.lwjgl:lwjgl-stb::$lwjglNatives"

    runtimeOnly "org.lwjgl:lwjgl:${{lwjglVersion}}:natives-windows"
    runtimeOnly "org.lwjgl:lwjgl:${{lwjglVersion}}:natives-windows-x86"
    runtimeOnly "org.lwjgl:lwjgl:${{lwjglVersion}}:natives-linux"
    runtimeOnly "org.lwjgl:lwjgl:${{lwjglVersion}}:natives-linux-arm64"
    runtimeOnly "org.lwjgl:lwjgl:${{lwjglVersion}}:natives-linux-arm32"
    runtimeOnly "org.lwjgl:lwjgl:${{lwjglVersion}}:natives-macos"
    runtimeOnly "org.lwjgl:lwjgl:${{lwjglVersion}}:natives-macos-arm64"

    runtimeOnly "org.lwjgl:lwjgl-glfw:${{lwjglVersion}}:natives-windows"
    runtimeOnly "org.lwjgl:lwjgl-glfw:${{lwjglVersion}}:natives-linux"
    runtimeOnly "org.lwjgl:lwjgl-glfw:${{lwjglVersion}}:natives-macos"
    runtimeOnly "org.lwjgl:lwjgl-opengl:${{lwjglVersion}}:natives-windows"
    runtimeOnly "org.lwjgl:lwjgl-opengl:${{lwjglVersion}}:natives-linux"
    runtimeOnly "org.lwjgl:lwjgl-opengl:${{lwjglVersion}}:natives-macos"
}}

test {{
    useJUnitPlatform()
}}

shadowJar {{
    archiveBaseName.set('{artifact_name}')
    archiveClassifier.set('')
    archiveVersion.set('1.0')
    manifest {{
        attributes 'Multi-Release': 'true'
        attributes 'Main-Class': '{desktop_main_package}.Main'
    }}
}}
"""

GAME_BUILD_TEMPLATE = """\
plugins {{
    id 'java'
}}

group = '{desktop_group}'
version = '1.0-SNAPSHOT'

dependencies {{
    implementation files("../libs/core.jar")
}}

test {{
    useJUnitPlatform()
}}
"""

DESKTOP_MAIN_TEMPLATE = """\
package {desktop_main_package};

import com.nikitos.platform.DesktopLauncher;
import com.nikitos.platformBridge.LauncherParams;
import {game_package}.MainRenderer;

public class Main {{
    public static void main(String[] args) {{
        LauncherParams launcherParams = new LauncherParams()
                .setWindowTitle("{desktop_project_name}")
                .setFullScreen(false)
                .setDebug(true)
                .setStartPage(unused -> new MainRenderer());
        DesktopLauncher desktopLauncher = new DesktopLauncher(launcherParams);
        desktopLauncher.run();
    }}
}}
"""

GAME_RENDERER_TEMPLATE = """\
package {game_package};

import com.nikitos.CoreRenderer;
import com.nikitos.GamePageClass;
import com.nikitos.main.camera.Camera;
import com.nikitos.main.images.PImage;
import com.nikitos.main.images.TextAlign;
import com.nikitos.main.shaders.Shader;
import com.nikitos.main.shaders.default_adaptors.MainShaderAdaptor;
import com.nikitos.main.vertices.SimplePolygon;
import com.nikitos.maths.Matrix;
import com.nikitos.utils.Utils;

import java.util.List;
import java.util.function.Function;

public class MainRenderer extends GamePageClass {{
    private Camera camera;
    private final Shader shader;
    private final SimplePolygon windowPolygon;

    private float screenWidth;
    private float screenHeight;
    private float windowWidth;
    private float windowHeight;

    public MainRenderer() {{
        shader = new Shader(
                "vertex_shader_engine.glsl",
                "fragment_shader_engine.glsl",
                this,
                new MainShaderAdaptor()
        );
        windowPolygon = new SimplePolygon(redrawWindow, false, 0, this);
    }}

    @Override
    public void onSurfaceChanged(int width, int height) {{
        screenWidth = width;
        screenHeight = height;
        windowWidth = Math.max(320f, Math.min(width * 0.7f, 720f * Utils.getKx()));
        windowHeight = Math.max(220f, Math.min(height * 0.55f, 420f * Utils.getKy()));

        camera = new Camera(width, height);
        camera.resetFor2d();

        windowPolygon.setRedrawNeeded(true);
        windowPolygon.redrawNow();
    }}

    @Override
    public void draw() {{
        Utils.background(22, 24, 32);
        CoreRenderer.engine.glClear();

        shader.apply();
        camera.resetFor2d();
        camera.apply();
        Matrix.applyMatrix(Matrix.resetTranslateMatrix(new float[16]));

        float x = (screenWidth - windowWidth) * 0.5f;
        float y = (screenHeight - windowHeight) * 0.5f;
        windowPolygon.prepareAndDraw(x, y, windowWidth, windowHeight, 0.1f);
    }}

    @Override
    public void onResume() {{
    }}

    @Override
    public void onPause() {{
    }}

    private final Function<List<Object>, PImage> redrawWindow = unused -> {{
        windowWidth = Utils.getX();
        windowHeight = Utils.getY();
        float k = Math.max(1f, Math.min(Utils.getKx(), Utils.getKy()));
        float titleBarHeight = 48f * k;
        float radius = 18f * k;
        float paddingX = 28f * k;
        float paddingY = 26f * k;
        windowWidth = Utils.getX();
        windowHeight = Utils.getY();
        PImage image = new PImage(windowWidth, windowHeight);
        image.clear();
        image.setAntiAlias(true);

        image.noStroke();
        image.fill(232, 236, 242, 255);
        image.roundRect(0, 0, windowWidth, windowHeight, radius, radius);

        image.fill(55, 65, 81, 255);
        image.roundRect(0, 0, windowWidth, titleBarHeight + radius * 0.4f, radius, radius);
        image.rect(0, titleBarHeight * 0.5f, windowWidth, titleBarHeight);

        image.fill(255, 255, 255, 255);
        image.textAlign(TextAlign.LEFT);
        image.textSize(18f * k);
        image.text("Seal Engine Starter", Utils.getX()/2, 31f * k);

        image.fill(17, 24, 39, 255);
        image.textSize(34f * k);
        image.text("Hello, world!", paddingX, titleBarHeight + 70f * k);

        image.fill(71, 85, 105, 255);
        image.textSize(18f * k);
        image.text(
                "Edit " + "{game_package}.MainRenderer" + " to build your first page.",
                paddingX,
                titleBarHeight + 116f * k
        );

        image.fill(59, 130, 246, 255);
        image.roundRect(
                paddingX,
                windowHeight - paddingY - 54f * k,
                190f * k,
                38f * k,
                12f * k,
                12f * k
        );
        image.fill(255, 255, 255, 255);
        image.textSize(16f * k);
        image.text("GamePage ready", paddingX + 20f * k, windowHeight - paddingY - 31f * k * 1.5f);

        return image;
    }};
}}
"""

KEEP_TEMPLATE = "Generated by seal_app_generator.\n"

ANDROID_SETTINGS_TEMPLATE = """\
pluginManagement {{
    repositories {{
        google {{
            content {{
                includeGroupByRegex("com\\\\.android.*")
                includeGroupByRegex("com\\\\.google.*")
                includeGroupByRegex("androidx.*")
            }}
        }}
        mavenCentral()
        gradlePluginPortal()
    }}
}}
dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}

rootProject.name = "{android_project_name}"
include ':app'
include(':game')
project(':game').projectDir = file('../desktop/game')
"""

ANDROID_TOP_LEVEL_BUILD_TEMPLATE = """\
plugins {{
    alias(libs.plugins.android.application) apply false
}}
"""

ANDROID_GRADLE_PROPERTIES_TEMPLATE = """\
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
android.nonTransitiveRClass=true
"""

ANDROID_VERSIONS_TEMPLATE = """\
[versions]
agp = "8.11.2"
junit = "4.13.2"
junitVersion = "1.3.0"
espressoCore = "3.7.0"
appcompat = "1.7.1"
material = "1.13.0"
activity = "1.13.0"
constraintlayout = "2.2.1"

[libraries]
junit = {{ group = "junit", name = "junit", version.ref = "junit" }}
ext-junit = {{ group = "androidx.test.ext", name = "junit", version.ref = "junitVersion" }}
espresso-core = {{ group = "androidx.test.espresso", name = "espresso-core", version.ref = "espressoCore" }}
appcompat = {{ group = "androidx.appcompat", name = "appcompat", version.ref = "appcompat" }}
material = {{ group = "com.google.android.material", name = "material", version.ref = "material" }}
activity = {{ group = "androidx.activity", name = "activity", version.ref = "activity" }}
constraintlayout = {{ group = "androidx.constraintlayout", name = "constraintlayout", version.ref = "constraintlayout" }}

[plugins]
android-application = {{ id = "com.android.application", version.ref = "agp" }}
"""

ANDROID_APP_BUILD_TEMPLATE = """\
plugins {{
    alias(libs.plugins.android.application)
}}

android {{
    namespace '{android_package}'
    compileSdk 36

    defaultConfig {{
        applicationId "{android_package}"
        minSdk 24
        targetSdk 36
        versionCode 1
        versionName "1.0"

        testInstrumentationRunner "androidx.test.runner.AndroidJUnitRunner"
    }}

    sourceSets {{
        main {{
            assets.srcDirs += [
                    '../../desktop/game/src/main/resources',
                    '../../desktop/src/main/resources'
            ]
        }}
    }}

    aaptOptions {{
        noCompress 'mp3', 'wav', 'ogg', 'obj', 'mtl', 'blend', 'ttf', 'otf'
    }}

    buildTypes {{
        release {{
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }}
    }}
    compileOptions {{
        sourceCompatibility JavaVersion.VERSION_11
        targetCompatibility JavaVersion.VERSION_11
    }}
}}

dependencies {{
    implementation project(":game")
    implementation libs.appcompat
    implementation libs.material
    implementation libs.activity
    implementation libs.constraintlayout
    implementation files('../../desktop/libs/core.jar')
    implementation files('libs/android.aar')
    implementation files('libs/obj-0.4.0.jar')
    testImplementation libs.junit
    androidTestImplementation libs.ext.junit
    androidTestImplementation libs.espresso.core
}}
"""

ANDROID_MANIFEST_TEMPLATE = """\
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <application
        android:allowBackup="true"
        android:dataExtractionRules="@xml/data_extraction_rules"
        android:fullBackupContent="@xml/backup_rules"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.SealGeneratedMobile">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>

</manifest>
"""

ANDROID_MAIN_ACTIVITY_TEMPLATE = """\
package {android_package};

import android.annotation.SuppressLint;
import android.opengl.GLSurfaceView;
import android.os.Bundle;
import android.view.MotionEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;

import androidx.appcompat.app.AppCompatActivity;

import com.nikitos.Engine;
import com.nikitos.main.touch.TouchProcessor;
import com.seal.gl_engine.platform.AndroidLauncher;
import com.seal.gl_engine.platform.AndroidLauncherParams;
import com.seal.gl_engine.touch.AndroidMotionEventAdapter;

import {game_package}.MainRenderer;

public class MainActivity extends AppCompatActivity implements View.OnTouchListener {{
    private Engine engine;

    @SuppressLint("ClickableViewAccessibility")
    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);

        AndroidLauncherParams androidLauncherParams = new AndroidLauncherParams(getApplicationContext())
                .setDebug(false)
                .setStartPage(unused -> new MainRenderer())
                .setMSAA(true);

        AndroidLauncher androidLauncher = new AndroidLauncher(androidLauncherParams);
        engine = androidLauncher.getEngine();

        requestWindowFeature(Window.FEATURE_NO_TITLE);
        Window window = getWindow();
        window.setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        int uiOptions = View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_FULLSCREEN;
        window.getDecorView().setSystemUiVisibility(uiOptions);

        GLSurfaceView surfaceView = androidLauncher.launch();
        setContentView(surfaceView);
        surfaceView.setOnTouchListener(this);
    }}

    @Override
    protected void onPause() {{
        super.onPause();
        engine.onPause();
    }}

    @Override
    protected void onResume() {{
        super.onResume();
        engine.onResume();
    }}

    @Override
    public boolean onTouch(View view, MotionEvent event) {{
        TouchProcessor.onTouch(new AndroidMotionEventAdapter(event));
        return true;
    }}
}}
"""

ANDROID_STRINGS_TEMPLATE = """\
<resources>
    <string name="app_name">{android_project_name}</string>
</resources>
"""

ANDROID_THEMES_TEMPLATE = """\
<resources xmlns:tools="http://schemas.android.com/tools">
    <style name="Base.Theme.SealGeneratedMobile" parent="Theme.Material3.DayNight.NoActionBar">
    </style>

    <style name="Theme.SealGeneratedMobile" parent="Base.Theme.SealGeneratedMobile" />
</resources>
"""

ANDROID_THEMES_NIGHT_TEMPLATE = """\
<resources xmlns:tools="http://schemas.android.com/tools">
    <style name="Base.Theme.SealGeneratedMobile" parent="Theme.Material3.DayNight.NoActionBar">
    </style>
</resources>
"""

ANDROID_LAYOUT_TEMPLATE = """\
<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    xmlns:tools="http://schemas.android.com/tools"
    android:id="@+id/main"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    tools:context=".MainActivity">

    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Hello World!"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toTopOf="parent" />

</androidx.constraintlayout.widget.ConstraintLayout>
"""

PROGUARD_TEMPLATE = """\
# Add project specific ProGuard rules here.
"""

WORKSPACE_README_TEMPLATE = """\
# {desktop_project_name}

Generated by `seal_app_generator`.

## Layout

- `desktop/` - desktop Gradle project with the launcher and shared `game` module
- `android/` - Android Gradle project that reuses `../desktop/game`

## Default Output

The generator now writes projects to `/home/nikita/IdeaProjects/` unless `--output-dir` is provided.

## Quick Start

Desktop build:

```bash
cd desktop
./gradlew shadowJar
```

Android build:

```bash
cd android
./gradlew assembleDebug
```

The starter page lives in `desktop/game/src/main/java/.../MainRenderer.java`.
"""

ANDROID_UNIT_TEST_TEMPLATE = """\
package {android_package};

import org.junit.Test;

import static org.junit.Assert.assertEquals;

public class ExampleUnitTest {{
    @Test
    public void addition_isCorrect() {{
        assertEquals(4, 2 + 2);
    }}
}}
"""

ANDROID_INSTRUMENTED_TEST_TEMPLATE = """\
package {android_package};

import android.content.Context;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import static org.junit.Assert.assertEquals;

@RunWith(AndroidJUnit4.class)
public class ExampleInstrumentedTest {{
    @Test
    public void useAppContext() {{
        Context appContext = InstrumentationRegistry.getInstrumentation().getTargetContext();
        assertEquals("{android_package}", appContext.getPackageName());
    }}
}}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Seal Engine workspace with separate desktop/ and android/ application folders."
    )
    parser.add_argument("project_name", help="Workspace name and default desktop Gradle project name.")
    parser.add_argument(
        "--output-dir",
        default="/home/nikita/IdeaProjects/",
        help="Parent directory where the workspace folder will be created. Default: /home/nikita/IdeaProjects/",
    )
    parser.add_argument(
        "--desktop-package",
        help="Java package for the desktop launcher. Default: com.example.<project_slug>.desktop",
    )
    parser.add_argument(
        "--game-package",
        help="Java package for the shared game module in desktop/game. Default: com.example.<project_slug>.game",
    )
    parser.add_argument(
        "--android-package",
        help="Android applicationId and namespace. Default: com.example.<project_slug>.mobile",
    )
    parser.add_argument(
        "--android-name",
        help="Android Gradle rootProject.name and app label. Default: <project_name> Android",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the existing workspace folder if it already exists.",
    )
    parser.add_argument(
        "--skip-engine-update",
        action="store_true",
        help="Skip downloading the latest Seal-Engine-3M release and updating engine binaries/docs after generation.",
    )
    return parser.parse_args()


def sanitize_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if not slug:
        slug = "seal_app"
    if slug[0].isdigit():
        slug = f"app_{slug}"
    return slug


def ensure_package(value: str) -> str:
    parts = []
    for part in value.split("."):
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", part).lower()
        if not cleaned:
            continue
        if cleaned[0].isdigit():
            cleaned = f"p_{cleaned}"
        parts.append(cleaned)
    if len(parts) < 2:
        raise ValueError(f"Package '{value}' is too short.")
    return ".".join(parts)


def render(template: str, **context: str) -> str:
    return template.format(**context)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    for item in src.rglob("*"):
        relative = item.relative_to(src)
        target = dst / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def reset_target(path: Path, force: bool) -> None:
    if not path.exists():
        return
    if not force:
        raise FileExistsError(f"Refusing to overwrite existing path: {path}")
    shutil.rmtree(path)


def extract_payload() -> Path:
    if PAYLOAD_SOURCE_DIR.exists():
        return PAYLOAD_SOURCE_DIR
    if not PAYLOAD_ARCHIVE.exists():
        raise FileNotFoundError(f"Missing template source directory and payload archive in {SCRIPT_DIR}")
    temp_dir = Path(tempfile.mkdtemp(prefix="seal_generator_payload_"))
    with zipfile.ZipFile(PAYLOAD_ARCHIVE) as archive:
        archive.extractall(temp_dir)
    payload_root = temp_dir / "template_src"
    if not payload_root.exists():
        raise FileNotFoundError(f"Archive does not contain template_src/: {PAYLOAD_ARCHIVE}")
    return payload_root


def copy_engine_docs(payload_root: Path, destination_root: Path) -> None:
    docs_dir = payload_root / "shared" / "docs"
    copy_file(docs_dir / "PROJECT_MAP_FOR_CODEX.md", destination_root / "PROJECT_MAP_FOR_CODEX.md")
    copy_file(docs_dir / "README.md", destination_root / "README.md")
    copy_file(docs_dir / "README.md", destination_root / "ENGINE-README.md")


def create_workspace_docs(payload_root: Path, workspace_root: Path, context: dict[str, str]) -> None:
    docs_dir = payload_root / "shared" / "docs"
    copy_file(docs_dir / "PROJECT_MAP_FOR_CODEX.md", workspace_root / "PROJECT_MAP_FOR_CODEX.md")
    copy_file(docs_dir / "README.md", workspace_root / "ENGINE-README.md")
    write_text(workspace_root / "README.md", render(WORKSPACE_README_TEMPLATE, **context))


def package_path(package_name: str) -> Path:
    return Path(*package_name.split("."))


def create_desktop_project(payload_root: Path, root: Path, context: dict[str, str]) -> None:
    copy_tree(payload_root / "desktop", root)
    copy_tree(payload_root / "shared" / "libs" / "desktop", root / "libs")
    copy_engine_docs(payload_root, root)

    write_text(root / "settings.gradle", render(DESKTOP_SETTINGS_TEMPLATE, **context))
    write_text(root / "build.gradle", render(DESKTOP_BUILD_TEMPLATE, **context))
    write_text(root / "game" / "build.gradle", render(GAME_BUILD_TEMPLATE, **context))
    write_text(
        root / "src" / "main" / "java" / package_path(context["desktop_main_package"]) / "Main.java",
        render(DESKTOP_MAIN_TEMPLATE, **context),
    )
    write_text(
        root / "game" / "src" / "main" / "java" / package_path(context["game_package"]) / "MainRenderer.java",
        render(GAME_RENDERER_TEMPLATE, **context),
    )
    write_text(root / "src" / "main" / "resources" / ".keep", KEEP_TEMPLATE)
    write_text(root / "game" / "src" / "main" / "resources" / ".keep", KEEP_TEMPLATE)
    make_executable(root / "gradlew")


def create_android_project(payload_root: Path, root: Path, context: dict[str, str]) -> None:
    copy_tree(payload_root / "android", root)
    copy_tree(payload_root / "shared" / "libs" / "android", root / "app" / "libs")
    copy_engine_docs(payload_root, root)

    shutil.rmtree(root / "app" / "src" / "test" / "java" / "template", ignore_errors=True)
    shutil.rmtree(root / "app" / "src" / "androidTest" / "java" / "template", ignore_errors=True)

    write_text(root / "settings.gradle", render(ANDROID_SETTINGS_TEMPLATE, **context))
    write_text(root / "build.gradle", render(ANDROID_TOP_LEVEL_BUILD_TEMPLATE, **context))
    write_text(root / "gradle.properties", render(ANDROID_GRADLE_PROPERTIES_TEMPLATE, **context))
    write_text(root / "gradle" / "libs.versions.toml", render(ANDROID_VERSIONS_TEMPLATE, **context))
    write_text(root / "app" / "build.gradle", render(ANDROID_APP_BUILD_TEMPLATE, **context))
    write_text(root / "app" / "proguard-rules.pro", render(PROGUARD_TEMPLATE, **context))
    write_text(root / "app" / "src" / "main" / "AndroidManifest.xml", render(ANDROID_MANIFEST_TEMPLATE, **context))
    write_text(
        root / "app" / "src" / "main" / "java" / package_path(context["android_package"]) / "MainActivity.java",
        render(ANDROID_MAIN_ACTIVITY_TEMPLATE, **context),
    )
    write_text(root / "app" / "src" / "main" / "res" / "layout" / "activity_main.xml", render(ANDROID_LAYOUT_TEMPLATE, **context))
    write_text(root / "app" / "src" / "main" / "res" / "values" / "strings.xml", render(ANDROID_STRINGS_TEMPLATE, **context))
    write_text(root / "app" / "src" / "main" / "res" / "values" / "themes.xml", render(ANDROID_THEMES_TEMPLATE, **context))
    write_text(root / "app" / "src" / "main" / "res" / "values-night" / "themes.xml", render(ANDROID_THEMES_NIGHT_TEMPLATE, **context))
    write_text(
        root / "app" / "src" / "test" / "java" / package_path(context["android_package"]) / "ExampleUnitTest.java",
        render(ANDROID_UNIT_TEST_TEMPLATE, **context),
    )
    write_text(
        root / "app" / "src" / "androidTest" / "java" / package_path(context["android_package"]) / "ExampleInstrumentedTest.java",
        render(ANDROID_INSTRUMENTED_TEST_TEMPLATE, **context),
    )
    make_executable(root / "gradlew")


def main() -> int:
    args = parse_args()

    project_name = args.project_name.strip()
    if not project_name:
        print("Project name must not be empty.", file=sys.stderr)
        return 1

    slug = sanitize_slug(project_name)
    desktop_package = ensure_package(args.desktop_package or f"com.example.{slug}.desktop")
    game_package = ensure_package(args.game_package or f"com.example.{slug}.game")
    android_package = ensure_package(args.android_package or f"com.example.{slug}.mobile")
    android_project_name = args.android_name or f"{project_name} Android"

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace_root = output_dir / project_name
    desktop_root = workspace_root / "desktop"
    android_root = workspace_root / "android"

    try:
        reset_target(workspace_root, args.force)
        workspace_root.mkdir(parents=True, exist_ok=True)
        payload_root = extract_payload()
        context = {
            "desktop_project_name": project_name,
            "android_project_name": android_project_name,
            "desktop_group": ".".join(desktop_package.split(".")[:-1]),
            "desktop_main_package": desktop_package,
            "game_package": game_package,
            "android_package": android_package,
            "artifact_name": sanitize_slug(project_name).replace("_", "-"),
        }

        create_workspace_docs(payload_root, workspace_root, context)
        create_desktop_project(payload_root, desktop_root, context)
        create_android_project(payload_root, android_root, context)

        if not args.skip_engine_update:
            try:
                from update_engine import update_workspace_engine

                tag = update_workspace_engine(workspace_root, verbose=True)
                print(f"Updated engine to release tag: {tag}")
            except Exception as exc:
                print(f"Engine update failed (generation still succeeded): {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"Generation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Workspace: {workspace_root}")
    print(f"Desktop project: {desktop_root}")
    print(f"Android project: {android_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
