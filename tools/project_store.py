#!/usr/bin/env python3
"""
Persistent SQLite-backed project and task store for Hermes-Orchestra.

Extends the Hermes SQLite state database (state.db) with projects/tasks tables.
Designed to share the same connection lifecycle as hermes_state.py.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECTS_SCHEMA_VERSION = 1
PROJECTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    client TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','archived','completed')),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""
TASKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    parent_task_id TEXT REFERENCES tasks(id),
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','in_progress','completed','cancelled','blocked')),
    assignee TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    deadline REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    completed_at REAL
);
"""
TASK_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    event_type TEXT NOT NULL,
    detail TEXT DEFAULT '',
    agent_output TEXT DEFAULT '',
    created_at REAL NOT NULL
);
"""


def _now() -> float:
    return time.time()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_db_path(db_path: Optional[Path] = None) -> Path:
    """Resolve the state.db path. Works inside Hermes (preferred) or standalone."""
    if db_path is not None:
        return Path(db_path)
    # Try Hermes home first
    try:
        from hermes_constants import get_hermes_home
        return get_hermes_home() / "state.db"
    except (ImportError, ModuleNotFoundError):
        pass
    # Fallback: env var or ~/.hermes/state.db
    hermes_home = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
    return Path(hermes_home) / "state.db"


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open or reuse the Hermes state.db connection."""
    resolved = _resolve_db_path(db_path)
    conn = sqlite3.connect(str(resolved))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(PROJECTS_TABLE_SQL)
    conn.execute(TASKS_TABLE_SQL)
    conn.execute(TASK_EVENTS_SQL)
    # Schema version tracking (simple: add column if not exists pattern)
    conn.commit()


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def project_create(name: str, description: str = "", client: str = "") -> dict:
    conn = _connect()
    try:
        pid = f"proj-{int(_now())}-{name.lower().replace(' ', '-')[:20]}"
        now = _now()
        conn.execute(
            "INSERT INTO projects (id, name, description, client, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (pid, name, description, client, now, now),
        )
        conn.commit()
        return {"ok": True, "project": project_get(pid)}
    finally:
        conn.close()


def project_get(project_id: str) -> Optional[dict]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def project_list(status: Optional[str] = None, client: Optional[str] = None) -> list:
    conn = _connect()
    try:
        parts = ["SELECT * FROM projects WHERE 1=1"]
        params = []
        if status:
            parts.append("AND status = ?")
            params.append(status)
        if client:
            parts.append("AND client = ?")
            params.append(client)
        parts.append("ORDER BY updated_at DESC")
        rows = conn.execute(" ".join(parts), params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def project_update(project_id: str, **kwargs) -> Optional[dict]:
    allowed = {"name", "description", "client", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return project_get(project_id)
    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [project_id]
    conn = _connect()
    try:
        conn.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", vals)
        conn.commit()
        return project_get(project_id)
    finally:
        conn.close()


def project_delete(project_id: str) -> dict:
    conn = _connect()
    try:
        conn.execute("UPDATE projects SET status = 'archived', updated_at = ? WHERE id = ?", (_now(), project_id))
        conn.execute("UPDATE tasks SET status = 'cancelled', updated_at = ? WHERE project_id = ? AND status NOT IN ('completed','cancelled')", (_now(), project_id))
        conn.commit()
        return {"ok": True, "project_id": project_id, "status": "archived"}
    finally:
        conn.close()


def project_stats(project_id: str) -> dict:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks WHERE project_id = ? GROUP BY status",
            (project_id,),
        ).fetchall()
        counts = {r["status"]: r["cnt"] for r in rows}
        total = sum(counts.values())
        return {
            "total": total,
            "pending": counts.get("pending", 0),
            "in_progress": counts.get("in_progress", 0),
            "completed": counts.get("completed", 0),
            "cancelled": counts.get("cancelled", 0),
            "blocked": counts.get("blocked", 0),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def _next_task_id() -> str:
    return f"task-{int(_now() * 1000)}"


def task_create(project_id: str, title: str, description: str = "", parent_task_id: Optional[str] = None) -> dict:
    conn = _connect()
    try:
        # Validate project exists
        proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not proj:
            return {"ok": False, "error": f"Project '{project_id}' not found"}
        tid = _next_task_id()
        now = _now()
        conn.execute(
            "INSERT INTO tasks (id, project_id, parent_task_id, title, description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (tid, project_id, parent_task_id, title, description, now, now),
        )
        conn.commit()
        return {"ok": True, "task": task_get(tid)}
    finally:
        conn.close()


def task_get(task_id: str) -> Optional[dict]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def task_list(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    parent_task_id: Optional[str] = None,
) -> list:
    conn = _connect()
    try:
        parts = ["SELECT * FROM tasks WHERE 1=1"]
        params = []
        if project_id:
            parts.append("AND project_id = ?")
            params.append(project_id)
        if status:
            parts.append("AND status = ?")
            params.append(status)
        if assignee:
            parts.append("AND assignee = ?")
            params.append(assignee)
        if parent_task_id is not None:
            parts.append("AND parent_task_id = ?")
            params.append(parent_task_id)
        parts.append("ORDER BY created_at ASC")
        rows = conn.execute(" ".join(parts), params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def task_update(task_id: str, **kwargs) -> Optional[dict]:
    allowed = {"title", "description", "status", "assignee", "priority", "deadline"}
    updates = {}
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            updates[k] = v
    if not updates:
        return task_get(task_id)
    now = _now()
    updates["updated_at"] = now
    if updates.get("status") == "completed":
        updates["completed_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [task_id]
    conn = _connect()
    try:
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", vals)
        conn.commit()
        return task_get(task_id)
    finally:
        conn.close()


def task_breakdown(parent_task_id: str, subtasks: List[Dict[str, str]]) -> dict:
    """Atomically split a parent task into subtasks."""
    parent = task_get(parent_task_id)
    if not parent:
        return {"ok": False, "error": f"Task '{parent_task_id}' not found"}
    created = []
    for sub in subtasks:
        result = task_create(
            project_id=parent["project_id"],
            title=sub.get("title", "(untitled)"),
            description=sub.get("description", ""),
            parent_task_id=parent_task_id,
        )
        if result.get("ok"):
            created.append(result["task"])
    # Mark parent as in_progress if it was pending
    if parent["status"] == "pending":
        task_update(parent_task_id, status="in_progress")
    return {"ok": True, "parent_task": parent_task_id, "subtasks": created, "count": len(created)}


def task_assign(task_id: str, assignee: str) -> Optional[dict]:
    return task_update(task_id, assignee=assignee)


def task_delete(task_id: str) -> dict:
    conn = _connect()
    try:
        conn.execute("UPDATE tasks SET status = 'cancelled', updated_at = ? WHERE id = ?", (_now(), task_id))
        conn.commit()
        return {"ok": True, "task_id": task_id, "status": "cancelled"}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Events / History
# ---------------------------------------------------------------------------

def task_event_add(task_id: str, event_type: str, detail: str = "", agent_output: str = "") -> dict:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO task_events (task_id, event_type, detail, agent_output, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, event_type, detail, agent_output, _now()),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def task_event_list(task_id: str, limit: int = 50) -> list:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM task_events WHERE task_id = ? ORDER BY created_at DESC LIMIT ?",
            (task_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
