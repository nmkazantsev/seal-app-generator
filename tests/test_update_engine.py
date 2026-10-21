import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
import update_engine
from seal_engine_updater.discovery import discover_engine_targets
from seal_engine_updater.updater import update_project_engine


class FakeStdin(io.StringIO):
    def __init__(self, *, interactive: bool):
        super().__init__("")
        self.interactive = interactive

    def isatty(self) -> bool:
        return self.interactive


def touch(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class EngineDiscoveryTests(unittest.TestCase):
    def test_discovers_libraries_in_different_nested_project_layouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            desktop = root / "TankiDesktop"
            mobile = root / "TankiMobile"
            touch(desktop / "build.gradle", 'implementation files("libs/core.jar", "libs/desktop.jar")')
            touch(desktop / "game" / "build.gradle", 'implementation files("../libs/core.jar")')
            touch(mobile / "app" / "build.gradle", """
                implementation files('../../TankiDesktop/libs/core.jar')
                implementation files('libs/android.aar', 'libs/obj-0.4.0.jar')
            """)
            core = touch(desktop / "libs" / "core.jar")
            desktop_jar = touch(desktop / "libs" / "desktop.jar")
            android_aar = touch(mobile / "app" / "libs" / "android.aar")
            obj_jar = touch(mobile / "app" / "libs" / "obj-0.4.0.jar")

            found = discover_engine_targets(root)

            self.assertEqual(found["core.jar"], {core.resolve()})
            self.assertEqual(found["desktop.jar"], {desktop_jar.resolve()})
            self.assertEqual(found["android.aar"], {android_aar.resolve()})
            self.assertEqual(found["obj-0.4.0.jar"], {obj_jar.resolve()})

    def test_fallback_finds_known_artifacts_and_ignores_generated_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library = touch(root / "app" / "libs" / "core.jar")
            touch(root / "app" / "build" / "generated" / "libs" / "desktop.jar")
            touch(root / ".git" / "objects" / "libs" / "android.aar")

            found = discover_engine_targets(root)

            self.assertEqual(found, {"core.jar": {library.resolve()}})

    def test_does_not_discover_gradle_references_outside_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "project"
            outside_jar = touch(parent / "outside" / "libs" / "core.jar")
            touch(root / "app" / "build.gradle", "implementation files('../../outside/libs/core.jar')")

            found = discover_engine_targets(root)

            self.assertNotIn("core.jar", found)
            self.assertTrue(outside_jar.is_file())


class EngineUpdaterCliTests(unittest.TestCase):
    def test_legacy_generator_import_still_exposes_update_function(self):
        self.assertIs(update_engine.update_workspace_engine, update_project_engine)

    def test_omitted_path_uses_current_directory_only_after_confirmation(self):
        root = Path.cwd().resolve()
        with patch.object(main.sys, "stdin", FakeStdin(interactive=True)):
            with patch("builtins.input", return_value="y"):
                with patch.object(main, "update_project_engine", return_value="v-test") as update:
                    result = main.main([])

        self.assertEqual(result, 0)
        update.assert_called_once_with(root, repo="nmkazantsev/Seal-Engine-3M", token=None, verbose=True)

    def test_declined_path_confirmation_cancels_without_updating(self):
        with patch.object(main.sys, "stdin", FakeStdin(interactive=True)):
            with patch("builtins.input", return_value="n"):
                with patch.object(main, "update_project_engine") as update:
                    result = main.main([])

        self.assertEqual(result, 1)
        update.assert_not_called()

    def test_omitted_path_in_non_interactive_run_fails_before_update(self):
        with patch.object(main.sys, "stdin", FakeStdin(interactive=False)):
            with patch.object(main, "update_project_engine") as update:
                result = main.main([])

        self.assertEqual(result, 2)
        update.assert_not_called()

    def test_consumer_update_preserves_application_readme_and_project_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touch(root / "build.gradle", 'implementation files("libs/core.jar")')
            touch(root / "libs" / "core.jar", "old core")
            readme = touch(root / "README.md", "application readme")
            project_map = touch(root / "PROJECT_MAP_FOR_CODEX.md", "application map")
            engine_readme = touch(root / "ENGINE-README.md", "old engine readme")
            internals = touch(root / "ENGINE_INTERNALS_MAP_FOR_CODEX.md", "old internals map")
            release = {
                "tag_name": "v-test",
                "assets": [{"name": "core.jar", "browser_download_url": "https://example.invalid/core.jar"}],
            }
            engine_docs = {
                "ENGINE_README": "new engine readme",
                "PROJECT_MAP_FOR_CODEX": "new engine map",
                "ENGINE_INTERNALS_MAP_FOR_CODEX": "new engine internals",
            }

            with patch("seal_engine_updater.updater.get_latest_release", return_value=(release, engine_docs)):
                with patch(
                    "seal_engine_updater.updater.download_asset",
                    side_effect=lambda url, destination, token=None: destination.write_bytes(b"new core"),
                ):
                    tag = update_project_engine(root)

            self.assertEqual(tag, "v-test")
            self.assertEqual(readme.read_text(encoding="utf-8"), "application readme")
            self.assertEqual(project_map.read_text(encoding="utf-8"), "application map")
            self.assertEqual(engine_readme.read_text(encoding="utf-8"), "new engine readme")
            self.assertEqual(internals.read_text(encoding="utf-8"), "new engine internals")
            self.assertEqual((root / "libs" / "core.jar").read_bytes(), b"new core")


if __name__ == "__main__":
    unittest.main()
