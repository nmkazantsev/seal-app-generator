from __future__ import annotations

import io
import json
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
import re

from .errors import UpdateEngineError

GITHUB_API_BASE = "https://api.github.com"


def _http_request(url: str, *, token: str | None = None, accept: str | None = None) -> urllib.request.Request:
    headers = {"User-Agent": "seal_app_generator/update_engine.py"}
    if accept:
        headers["Accept"] = accept
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def _http_get_json(url: str, *, token: str | None = None) -> dict:
    request = _http_request(url, token=token, accept="application/vnd.github+json")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        raise UpdateEngineError(f"GitHub API error {exc.code} for {url}: {body or exc.reason}") from exc
    except Exception as exc:
        raise UpdateEngineError(f"Failed to fetch {url}: {exc}") from exc


def download_asset(url: str, destination: Path, *, token: str | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = _http_request(url, token=token)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _read_zip_member(archive: zipfile.ZipFile, suffix: str) -> str | None:
    for name in archive.namelist():
        if name.endswith("/" + suffix) or name.endswith(suffix):
            with archive.open(name) as member:
                return member.read().decode("utf-8", errors="replace")
    return None


def _fetch_engine_docs(release: dict, *, token: str | None = None) -> dict[str, str]:
    zipball_url = release.get("zipball_url")
    if not zipball_url:
        raise UpdateEngineError("Release JSON did not contain zipball_url.")
    request = _http_request(zipball_url, token=token, accept="application/vnd.github+json")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read()
    except Exception as exc:
        raise UpdateEngineError(f"Failed to download release zipball: {exc}") from exc

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        readme = _read_zip_member(archive, "sealEngine_3M/README.md") or _read_zip_member(archive, "README.md")
        project_map = _read_zip_member(archive, "sealEngine_3M/PROJECT_MAP_FOR_CODEX.md") or _read_zip_member(
            archive, "PROJECT_MAP_FOR_CODEX.md"
        )
        internals_map = _read_zip_member(
            archive, "sealEngine_3M/ENGINE_INTERNALS_MAP_FOR_CODEX.md"
        ) or _read_zip_member(archive, "ENGINE_INTERNALS_MAP_FOR_CODEX.md")

    found = {"README": readme, "PROJECT_MAP": project_map, "ENGINE_INTERNALS_MAP": internals_map}
    missing = [name for name, content in found.items() if not content]
    if missing:
        raise UpdateEngineError(f"Missing docs in engine zipball: {', '.join(missing)}")
    return {
        "ENGINE_README": readme,
        "PROJECT_MAP_FOR_CODEX": project_map,
        "ENGINE_INTERNALS_MAP_FOR_CODEX": internals_map,
    }


def get_latest_release(repo: str, token: str | None = None) -> tuple[dict, dict[str, str]]:
    release = _http_get_json(f"{GITHUB_API_BASE}/repos/{repo}/releases/latest", token=token)
    docs = _fetch_engine_docs(release, token=token)
    return release, docs


def find_release_asset(release: dict, *, wanted_name: str, patterns: list[str]) -> dict | None:
    assets = release.get("assets") or []
    if not isinstance(assets, list):
        return None
    for asset in assets:
        if asset.get("name") == wanted_name:
            return asset
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for pattern in compiled:
        for asset in assets:
            if pattern.search(asset.get("name") or ""):
                return asset
    return None
