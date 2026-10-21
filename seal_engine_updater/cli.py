from __future__ import annotations

import argparse
import os
from pathlib import Path

from .errors import UpdateEngineError

DEFAULT_REPO = "nmkazantsev/Seal-Engine-3M"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Update the latest Seal-Engine-3M release in a project by finding "
            "engine libraries referenced by Gradle or stored in libs/ folders."
        )
    )
    parser.add_argument(
        "workspace",
        nargs="?",
        help="Project root with Gradle references or libs/ folders; may contain multiple related app projects.",
    )
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub repo in owner/name form. Default: {DEFAULT_REPO}")
    parser.add_argument(
        "--github-token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub token for higher rate limits. Default: env GITHUB_TOKEN (optional).",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress non-error output.")
    return parser.parse_args(argv)


def resolve_cli_project_root(
    path: str | None,
    *,
    stdin_isatty: bool,
    input_fn=None,
    cwd: Path | None = None,
) -> Path | None:
    if path is not None:
        return Path(path).expanduser().resolve()
    if not stdin_isatty:
        raise UpdateEngineError(
            "Project path was omitted, but stdin is not interactive. Pass the project root as an argument."
        )

    current_dir = (cwd or Path.cwd()).resolve()
    try:
        ask = input if input_fn is None else input_fn
        answer = ask(
            f"Путь проекта не указан. Использовать текущую папку как корень проекта?\n"
            f"{current_dir}\nПродолжить? [y/N]: "
        )
    except EOFError as exc:
        raise UpdateEngineError("No confirmation received; update cancelled.") from exc
    if answer.strip().lower() not in {"y", "yes", "д", "да"}:
        return None
    return current_dir
