from __future__ import annotations

import os
import re
from pathlib import Path

from .errors import UpdateEngineError

ENGINE_ASSET_NAMES = {"core.jar", "desktop.jar", "android.aar", "obj-0.4.0.jar"}
IGNORED_DIRS = {".git", ".gradle", "build", "out", "target", "node_modules"}


def resolve_project_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if not root.is_dir():
        raise UpdateEngineError(f"Project root is not a directory: {root}")
    return root


def _iter_project_files(root: Path):
    """Walk project files, skipping VCS data and generated build output."""
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name not in IGNORED_DIRS)
        for filename in filenames:
            yield Path(current) / filename


def discover_engine_targets(project_root: Path) -> dict[str, set[Path]]:
    """Find existing engine library paths in Gradle files and libs/ folders."""
    root = resolve_project_root(project_root)
    targets = {name: set() for name in ENGINE_ASSET_NAMES}
    dependency_pattern = re.compile(
        r"(?P<quote>['\"])(?P<path>[^'\"\r\n]*(?:core|desktop|android|obj-0\.4\.0)\.(?:jar|aar))(?P=quote)",
        re.IGNORECASE,
    )

    gradle_names = {"build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"}
    for file_path in _iter_project_files(root):
        if file_path.name not in gradle_names:
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in dependency_pattern.finditer(text):
            relative_path = match.group("path").strip()
            # Gradle expressions need Gradle itself; this updater resolves literal paths.
            if "$" in relative_path:
                continue
            name = Path(relative_path).name.lower()
            candidate = (file_path.parent / relative_path).resolve()
            if name in targets and candidate.is_file() and candidate.is_relative_to(root):
                targets[name].add(candidate)

    # Some projects use fileTree("libs") instead of listing each library in Gradle.
    for file_path in _iter_project_files(root):
        if file_path.parent.name.lower() != "libs":
            continue
        name = file_path.name.lower()
        candidate = file_path.resolve()
        if name in targets and candidate.is_file() and candidate.is_relative_to(root):
            targets[name].add(candidate)

    return {name: paths for name, paths in targets.items() if paths}


def discover_engine_docs(project_root: Path) -> dict[str, set[Path]]:
    root = resolve_project_root(project_root)
    docs = {"ENGINE_README": set(), "ENGINE_INTERNALS_MAP_FOR_CODEX": set()}
    for file_path in _iter_project_files(root):
        if file_path.name == "ENGINE-README.md":
            docs["ENGINE_README"].add(file_path)
        elif file_path.name == "ENGINE_INTERNALS_MAP_FOR_CODEX.md":
            docs["ENGINE_INTERNALS_MAP_FOR_CODEX"].add(file_path)
    return docs


def is_generated_workspace(project_root: Path) -> bool:
    return (project_root / "desktop" / "libs").is_dir() and (project_root / "android" / "app" / "libs").is_dir()
