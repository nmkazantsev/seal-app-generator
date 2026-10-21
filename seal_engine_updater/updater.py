from __future__ import annotations

import datetime as _dt
import re
import shutil
import tempfile
from pathlib import Path

from .cli import DEFAULT_REPO
from .discovery import discover_engine_docs, discover_engine_targets, is_generated_workspace, resolve_project_root
from .errors import UpdateEngineError
from .github import download_asset, find_release_asset, get_latest_release

ENGINE_ASSETS = {
    "core.jar": [r"\bcore\b.*\.jar$"],
    "desktop.jar": [r"\bdesktop\b.*\.jar$"],
    "android.aar": [r"\bandroid\b.*\.aar$"],
    "obj-0.4.0.jar": [r"\bobj\b.*\.jar$"],
}


def _iso_to_local(iso: str) -> str:
    try:
        date = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return date.astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    except Exception:
        return iso


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _required_release_asset(release: dict, name: str) -> dict:
    asset = find_release_asset(release, wanted_name=name, patterns=ENGINE_ASSETS[name])
    if not asset:
        assets = release.get("assets") or []
        if not isinstance(assets, list):
            assets = []
        available = ", ".join(sorted({(item.get("name") or "").strip() for item in assets if item.get("name")})) or "<none>"
        raise UpdateEngineError(f"Missing release asset for {name}. Available assets: {available}")
    return asset


def update_project_engine(
    project_root: Path,
    *,
    repo: str = DEFAULT_REPO,
    token: str | None = None,
    verbose: bool = False,
) -> str:
    root = resolve_project_root(project_root)
    targets = discover_engine_targets(root)
    if not targets:
        raise UpdateEngineError(
            f"No Seal Engine libraries found under {root}. "
            "Pass a project root containing Gradle references or libs/ folders with known engine files."
        )

    release, docs = get_latest_release(repo, token)
    tag = release.get("tag_name") or "<unknown>"
    name = release.get("name") or ""
    published_at = release.get("published_at") or ""
    if verbose:
        title = f"{tag} ({name})" if name else tag
        when = _iso_to_local(published_at) if published_at else "unknown time"
        print(f"[update_engine] Latest release: {title} published {when}")

    asset_names = [name for name in targets if name != "obj-0.4.0.jar"]
    required_assets = {name: _required_release_asset(release, name) for name in asset_names}
    obj_asset = (
        find_release_asset(release, wanted_name="obj-0.4.0.jar", patterns=ENGINE_ASSETS["obj-0.4.0.jar"])
        if "obj-0.4.0.jar" in targets
        else None
    )

    with tempfile.TemporaryDirectory(prefix="seal_engine_update_") as temporary_dir:
        temporary_root = Path(temporary_dir)
        downloads = {name: (asset, temporary_root / name) for name, asset in required_assets.items()}
        if obj_asset:
            downloads["obj-0.4.0.jar"] = (obj_asset, temporary_root / "obj-0.4.0.jar")

        for output_name, (asset, destination) in downloads.items():
            url = asset.get("browser_download_url")
            if not url:
                raise UpdateEngineError(f"Asset {output_name} did not include browser_download_url.")
            if verbose:
                print(f"[update_engine] Downloading {output_name} ...")
            download_asset(url, destination, token=token)

        for artifact_name, paths in targets.items():
            downloaded = downloads.get(artifact_name)
            if downloaded is None:
                if verbose and artifact_name == "obj-0.4.0.jar":
                    print("[update_engine] Release has no obj-0.4.0.jar asset; keeping local copies.")
                continue
            for path in sorted(paths):
                if verbose:
                    print(f"[update_engine] Updating {path.relative_to(root)} ...")
                shutil.copy2(downloaded[1], path)

    if is_generated_workspace(root):
        _write_text(root / "ENGINE-README.md", docs["ENGINE_README"])
        _write_text(root / "PROJECT_MAP_FOR_CODEX.md", docs["PROJECT_MAP_FOR_CODEX"])
        _write_text(root / "ENGINE_INTERNALS_MAP_FOR_CODEX.md", docs["ENGINE_INTERNALS_MAP_FOR_CODEX"])
        for app_root in (root / "desktop", root / "android"):
            _write_text(app_root / "README.md", docs["ENGINE_README"])
            _write_text(app_root / "ENGINE-README.md", docs["ENGINE_README"])
            _write_text(app_root / "PROJECT_MAP_FOR_CODEX.md", docs["PROJECT_MAP_FOR_CODEX"])
            _write_text(app_root / "ENGINE_INTERNALS_MAP_FOR_CODEX.md", docs["ENGINE_INTERNALS_MAP_FOR_CODEX"])
    else:
        targets_by_name = discover_engine_docs(root)
        for path in sorted(targets_by_name["ENGINE_README"]):
            _write_text(path, docs["ENGINE_README"])
        for path in sorted(targets_by_name["ENGINE_INTERNALS_MAP_FOR_CODEX"]):
            _write_text(path, docs["ENGINE_INTERNALS_MAP_FOR_CODEX"])

    return tag
