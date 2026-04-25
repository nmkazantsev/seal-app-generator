#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as _dt
import io
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


GITHUB_API_BASE = "https://api.github.com"
DEFAULT_REPO = "nmkazantsev/Seal-Engine-3M"


class UpdateEngineError(RuntimeError):
    pass


def _iso_to_local(iso: str) -> str:
    try:
        # Example: 2026-04-12T01:23:45Z
        dt = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    except Exception:
        return iso


def _http_request(url: str, *, token: str | None = None, accept: str | None = None) -> urllib.request.Request:
    headers = {
        "User-Agent": "seal_app_generator/update_engine.py",
    }
    if accept:
        headers["Accept"] = accept
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def _http_get_json(url: str, *, token: str | None = None) -> dict:
    req = _http_request(url, token=token, accept="application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise UpdateEngineError(f"GitHub API error {exc.code} for {url}: {body or exc.reason}") from exc
    except Exception as exc:
        raise UpdateEngineError(f"Failed to fetch {url}: {exc}") from exc


def _download(url: str, dst: Path, *, token: str | None = None) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = _http_request(url, token=token)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, tmp.open("wb") as f:
            shutil.copyfileobj(resp, f)
        tmp.replace(dst)
    finally:
        tmp.unlink(missing_ok=True)


def _resolve_workspace_root(path: Path) -> Path:
    p = path.expanduser().resolve()
    if (p / "desktop").is_dir() and (p / "android").is_dir():
        return p
    if p.name in {"desktop", "android"} and (p.parent / "desktop").is_dir() and (p.parent / "android").is_dir():
        return p.parent
    raise UpdateEngineError(
        "Expected a Seal workspace root containing 'desktop/' and 'android/' (or a direct desktop/android subfolder)."
    )


def _find_asset(assets: list[dict], *, want_name: str, patterns: list[re.Pattern[str]]) -> dict | None:
    for asset in assets:
        if asset.get("name") == want_name:
            return asset
    for pat in patterns:
        for asset in assets:
            name = asset.get("name") or ""
            if pat.search(name):
                return asset
    return None


def _read_zip_member(zf: zipfile.ZipFile, suffix: str) -> str | None:
    # GitHub zipballs include a leading "<repo>-<sha>/" folder, so we match by suffix.
    for name in zf.namelist():
        if name.endswith("/" + suffix) or name.endswith(suffix):
            with zf.open(name) as f:
                data = f.read()
            return data.decode("utf-8", errors="replace")
    return None


def _fetch_engine_docs_from_release_zipball(release: dict, *, token: str | None = None) -> dict[str, str]:
    zipball_url = release.get("zipball_url")
    if not zipball_url:
        raise UpdateEngineError("Release JSON did not contain zipball_url.")

    req = _http_request(zipball_url, token=token, accept="application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read()
    except Exception as exc:
        raise UpdateEngineError(f"Failed to download release zipball: {exc}") from exc

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        readme = _read_zip_member(zf, "sealEngine_3M/README.md") or _read_zip_member(zf, "README.md")
        project_map = _read_zip_member(zf, "sealEngine_3M/PROJECT_MAP_FOR_CODEX.md") or _read_zip_member(
            zf, "PROJECT_MAP_FOR_CODEX.md"
        )
        internals_map = _read_zip_member(
            zf, "sealEngine_3M/ENGINE_INTERNALS_MAP_FOR_CODEX.md"
        ) or _read_zip_member(zf, "ENGINE_INTERNALS_MAP_FOR_CODEX.md")

    missing = [k for k, v in {"README": readme, "PROJECT_MAP": project_map, "ENGINE_INTERNALS_MAP": internals_map}.items() if not v]
    if missing:
        raise UpdateEngineError(f"Missing docs in engine zipball: {', '.join(missing)}")

    return {
        "ENGINE_README": readme,
        "PROJECT_MAP_FOR_CODEX": project_map,
        "ENGINE_INTERNALS_MAP_FOR_CODEX": internals_map,
    }


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def update_workspace_engine(
    workspace_root: Path,
    *,
    repo: str = DEFAULT_REPO,
    token: str | None = None,
    verbose: bool = False,
) -> str:
    """
    Updates a generated Seal workspace in-place:
    - desktop/libs/*.jar
    - android/app/libs/*.jar|*.aar
    - ENGINE_README (engine README content), PROJECT_MAP_FOR_CODEX.md, ENGINE_INTERNALS_MAP_FOR_CODEX.md

    Returns the resolved engine release tag.
    """

    workspace_root = _resolve_workspace_root(workspace_root)

    release = _http_get_json(f"{GITHUB_API_BASE}/repos/{repo}/releases/latest", token=token)
    tag = release.get("tag_name") or "<unknown>"
    name = release.get("name") or ""
    published_at = release.get("published_at") or ""
    if verbose:
        title = f"{tag} ({name})" if name else tag
        when = _iso_to_local(published_at) if published_at else "unknown time"
        print(f"[update_engine] Latest release: {title} published {when}")

    docs = _fetch_engine_docs_from_release_zipball(release, token=token)

    assets = release.get("assets") or []
    if not isinstance(assets, list):
        assets = []

    def must_asset(want_name: str, patterns: list[str]) -> dict:
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        asset = _find_asset(assets, want_name=want_name, patterns=compiled)
        if not asset:
            available = ", ".join(sorted({(a.get("name") or "").strip() for a in assets if a.get("name")})) or "<none>"
            raise UpdateEngineError(f"Missing release asset for {want_name}. Available assets: {available}")
        return asset

    def optional_asset(want_name: str, patterns: list[str]) -> dict | None:
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        return _find_asset(assets, want_name=want_name, patterns=compiled)

    core_asset = must_asset("core.jar", [r"\bcore\b.*\.jar$"])
    desktop_asset = must_asset("desktop.jar", [r"\bdesktop\b.*\.jar$"])
    android_asset = must_asset("android.aar", [r"\bandroid\b.*\.aar$"])
    # obj-0.4.0.jar is a third-party dependency; some engine releases may not ship it as an asset.
    obj_asset = optional_asset("obj-0.4.0.jar", [r"\bobj\b.*\.jar$"])

    with tempfile.TemporaryDirectory(prefix="seal_engine_update_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        downloads = {
            "core.jar": (core_asset, tmp_dir / "core.jar"),
            "desktop.jar": (desktop_asset, tmp_dir / "desktop.jar"),
            "android.aar": (android_asset, tmp_dir / "android.aar"),
        }
        if obj_asset:
            downloads["obj-0.4.0.jar"] = (obj_asset, tmp_dir / "obj-0.4.0.jar")

        for out_name, (asset, dst) in downloads.items():
            url = asset.get("browser_download_url")
            if not url:
                raise UpdateEngineError(f"Asset {out_name} did not include browser_download_url.")
            if verbose:
                print(f"[update_engine] Downloading {out_name} ...")
            _download(url, dst, token=token)

        desktop_libs = workspace_root / "desktop" / "libs"
        android_libs = workspace_root / "android" / "app" / "libs"

        shutil.copy2(downloads["core.jar"][1], desktop_libs / "core.jar")
        shutil.copy2(downloads["desktop.jar"][1], desktop_libs / "desktop.jar")
        if "obj-0.4.0.jar" in downloads:
            shutil.copy2(downloads["obj-0.4.0.jar"][1], desktop_libs / "obj-0.4.0.jar")
        elif not (desktop_libs / "obj-0.4.0.jar").exists():
            raise UpdateEngineError("obj-0.4.0.jar was not present in the release assets and is missing locally.")

        shutil.copy2(downloads["core.jar"][1], android_libs / "core.jar")
        shutil.copy2(downloads["android.aar"][1], android_libs / "android.aar")
        if "obj-0.4.0.jar" in downloads:
            shutil.copy2(downloads["obj-0.4.0.jar"][1], android_libs / "obj-0.4.0.jar")
        elif not (android_libs / "obj-0.4.0.jar").exists():
            raise UpdateEngineError("obj-0.4.0.jar was not present in the release assets and is missing locally.")

    engine_readme = docs["ENGINE_README"]
    project_map = docs["PROJECT_MAP_FOR_CODEX"]
    internals_map = docs["ENGINE_INTERNALS_MAP_FOR_CODEX"]

    # Workspace root: keep the generated workspace README.md intact; update only engine doc files.
    _write_text(workspace_root / "ENGINE-README.md", engine_readme)
    _write_text(workspace_root / "PROJECT_MAP_FOR_CODEX.md", project_map)
    _write_text(workspace_root / "ENGINE_INTERNALS_MAP_FOR_CODEX.md", internals_map)

    for app_root in (workspace_root / "desktop", workspace_root / "android"):
        _write_text(app_root / "README.md", engine_readme)
        _write_text(app_root / "ENGINE-README.md", engine_readme)
        _write_text(app_root / "PROJECT_MAP_FOR_CODEX.md", project_map)
        _write_text(app_root / "ENGINE_INTERNALS_MAP_FOR_CODEX.md", internals_map)

    return tag


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Update an existing Seal workspace to the latest Seal-Engine-3M release: "
            "refresh engine binaries (core.jar/desktop.jar/android.aar/obj) and engine docs."
        )
    )
    parser.add_argument(
        "workspace",
        help="Path to the generated workspace root (contains desktop/ and android/), or its desktop/ or android/ folder.",
    )
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub repo in owner/name form. Default: {DEFAULT_REPO}")
    parser.add_argument(
        "--github-token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub token for higher rate limits. Default: env GITHUB_TOKEN (optional).",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress non-error output.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    verbose = not args.quiet
    try:
        tag = update_workspace_engine(Path(args.workspace), repo=args.repo, token=args.github_token, verbose=verbose)
    except UpdateEngineError as exc:
        print(f"[update_engine] ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("[update_engine] Aborted.", file=sys.stderr)
        return 130

    if verbose:
        print(f"[update_engine] Done. Engine release tag: {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
