"""Snowflake connection wrapper for the RHS demo flow.

Reads the same `~/.snowflake/config.toml` connection that `snow` CLI
uses. We support PAT (programmatic-access-token) auth — the demo's
auth path on this account.

The connection is opened on first call and reused for the process
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


def _load_connection_config(name: str = "regulai") -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"{CONFIG_PATH} not found — run `snow connection add` first")
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
