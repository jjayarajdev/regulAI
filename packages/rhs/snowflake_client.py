"""Snowflake connection wrapper for the RHS demo flow.

Two auth paths, tried in order:

  1. Environment variables (used inside Docker / on AWS).
     Required: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and one of
     (SNOWFLAKE_PASSWORD, SNOWFLAKE_TOKEN).
     Optional: SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE,
     SNOWFLAKE_SCHEMA, SNOWFLAKE_AUTHENTICATOR (defaults to
     PROGRAMMATIC_ACCESS_TOKEN when SNOWFLAKE_TOKEN is set).

  2. `~/.snowflake/config.toml` — the same file `snow` CLI uses.
     Used on dev laptops. The `regulai` connection section.

If neither is available, raises RuntimeError on first connect. The
connection is opened lazily on first call and reused for the process
lifetime; FastAPI workers should call `close()` on shutdown.
"""

from __future__ import annotations

import os
import threading
import tomllib
from pathlib import Path
from typing import Any

import snowflake.connector

CONFIG_PATH = Path.home() / ".snowflake" / "config.toml"


def _from_env() -> dict[str, Any] | None:
    """If SNOWFLAKE_ACCOUNT is set, build a connection-config dict from
    environment variables (the Docker / AWS path). Returns None when
    SNOWFLAKE_ACCOUNT is absent — caller falls back to the toml file."""
    account = os.environ.get("SNOWFLAKE_ACCOUNT")
    if not account:
        return None

    cfg: dict[str, Any] = {
        "account": account,
        "user": os.environ.get("SNOWFLAKE_USER", ""),
    }
    # Optional but commonly-set
    for env_key, cfg_key in [
        ("SNOWFLAKE_ROLE", "role"),
        ("SNOWFLAKE_WAREHOUSE", "warehouse"),
        ("SNOWFLAKE_DATABASE", "database"),
        ("SNOWFLAKE_SCHEMA", "schema"),
        ("SNOWFLAKE_AUTHENTICATOR", "authenticator"),
    ]:
        val = os.environ.get(env_key)
        if val:
            cfg[cfg_key] = val

    # Credentials — exactly one of PAT (preferred for this account) or password
    if os.environ.get("SNOWFLAKE_TOKEN"):
        cfg["token"] = os.environ["SNOWFLAKE_TOKEN"]
        cfg.setdefault("authenticator", "PROGRAMMATIC_ACCESS_TOKEN")
    elif os.environ.get("SNOWFLAKE_PASSWORD"):
        cfg["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    return cfg


def _load_connection_config(name: str = "regulai") -> dict[str, Any]:
    # Env vars win when present (Docker / AWS path).
    env_cfg = _from_env()
    if env_cfg is not None:
        return env_cfg

    # Dev laptop fallback — the snow CLI's config.toml.
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            f"No Snowflake credentials. Set env vars "
            f"(SNOWFLAKE_ACCOUNT + SNOWFLAKE_USER + SNOWFLAKE_TOKEN or "
            f"SNOWFLAKE_PASSWORD) or run `snow connection add` to create "
            f"{CONFIG_PATH}."
        )
    with open(CONFIG_PATH, "rb") as fh:
        cfg = tomllib.load(fh)
    section = cfg.get("connections", {}).get(name)
    if not section:
        raise RuntimeError(f"connection {name!r} not found in {CONFIG_PATH}")
    return section


_lock = threading.Lock()
_conn: snowflake.connector.SnowflakeConnection | None = None


def get_connection() -> snowflake.connector.SnowflakeConnection:
    """Return a process-wide Snowflake connection (lazily opened)."""
    global _conn
    with _lock:
        if _conn is None or getattr(_conn, "is_closed", lambda: True)():
            cfg = _load_connection_config()
            kwargs: dict[str, Any] = {
                "account": cfg["account"],
                "user": cfg["user"],
                "role": cfg.get("role"),
                "warehouse": cfg.get("warehouse") or "COMPUTE_WH",
                "database": cfg.get("database") or "INSURANCE_REGULATORY",
            }
            authenticator = cfg.get("authenticator")
            if authenticator and authenticator.upper() == "PROGRAMMATIC_ACCESS_TOKEN":
                kwargs["authenticator"] = "PROGRAMMATIC_ACCESS_TOKEN"
                kwargs["token"] = cfg["token"]
            elif authenticator:
                kwargs["authenticator"] = authenticator
                if "password" in cfg:
                    kwargs["password"] = cfg["password"]
            else:
                kwargs["password"] = cfg["password"]
            _conn = snowflake.connector.connect(**kwargs)
        return _conn


def query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """Run a query, return rows as a list of dicts (column name → value)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0].lower() for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def close() -> None:
    """Close the cached connection (for tests / shutdown hooks)."""
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
