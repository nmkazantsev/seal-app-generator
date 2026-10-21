#!/usr/bin/env python3
"""Compatibility entry point for the Seal Engine updater."""

from main import main
from seal_engine_updater.updater import update_project_engine as update_workspace_engine


if __name__ == "__main__":
    raise SystemExit(main())
