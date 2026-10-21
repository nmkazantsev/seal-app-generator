#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from seal_engine_updater.cli import parse_args, resolve_cli_project_root
from seal_engine_updater.errors import UpdateEngineError
from seal_engine_updater.updater import update_project_engine


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    verbose = not args.quiet

    try:
        project_root = resolve_cli_project_root(
            args.workspace,
            stdin_isatty=sys.stdin.isatty(),
            cwd=Path.cwd(),
        )
        if project_root is None:
            print("[update_engine] Update cancelled.")
            return 1

        tag = update_project_engine(project_root, repo=args.repo, token=args.github_token, verbose=verbose)
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
    raise SystemExit(main())
