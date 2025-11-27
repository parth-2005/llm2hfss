"""Environment loading utilities used across the project.

This module provides a small, production-oriented helper to load .env files
in a predictable order and with sane defaults:

- If `DOTENV_PATH` is set it will load that path only.
- Otherwise it will attempt to load `.env.local` then `.env` from the
  current working directory (without overriding existing env vars).

The helper is optional: if `python-dotenv` is not installed the function
will silently no-op and environment variables must come from the OS.
"""

from typing import Optional
import os


def load_envs(dotenv_path: Optional[str] = None, override: bool = False) -> None:
    """Load environment variables from .env files.

    Args:
        dotenv_path: optional explicit path to a dotenv file. If provided,
            only that file is loaded.
        override: if True, values from dotenv files will overwrite existing
            environment variables. Default is False (do not override).
    """
    try:
        from dotenv import load_dotenv
    except Exception:
        # python-dotenv not installed; nothing to do
        return

    if dotenv_path:
        load_dotenv(dotenv_path, override=override)
        return

    # Allow users to control path via DOTENV_PATH env var
    env_path = os.environ.get("DOTENV_PATH")
    if env_path:
        load_dotenv(env_path, override=override)
        return

    # Standard order: .env.local then .env
    load_dotenv('.env.local', override=override)
    load_dotenv('.env', override=override)


def env_info(keys: Optional[list] = None) -> dict:
    """Return a small diagnostic dict about selected env vars.

    Values are masked for safety (only show presence and length).
    """
    keys = keys or []
    out = {}
    for k in keys:
        v = os.environ.get(k)
        out[k] = {"present": v is not None, "len": len(v) if v else 0}
    return out
