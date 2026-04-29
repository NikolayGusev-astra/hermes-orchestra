#!/usr/bin/env python3
"""
Project Management Tools for Hermes-Orchestra.

Provides persistent project CRUD operations backed by SQLite.
Auto-registers with the Hermes tool registry on import.
"""

import json
from typing import Any, Dict, List, Optional

from tools.project_store import (
    project_create as _create,
    project_get as _get,
    project_list as _list,
    project_update as _update,
    project_delete as _delete,
    project_stats as _stats,
)
from tools.registry import registry, tool_error

# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def handle_project_create(
    name: str,
    description: str = "",
    client: str = "",
) -> str:
    """Create a new project."""
    result = _create(name, description=description, client=client)
    return json.dumps(result, ensure_ascii=False, default=str)


def handle_project_get(project_id: str) -> str:
    """Get project details including statistics."""
    proj = _get(project_id)
    if proj is None:
        return json.dumps({"ok": False, "error": f"Project '{project_id}' not found"})
    stats = _stats(project_id)
    proj["stats"] = stats
    return json.dumps({"ok": True, "project": proj}, ensure_ascii=False, default=str)


def handle_project_list(
    status: Optional[str] = None,
    client: Optional[str] = None,
) -> str:
    """List all projects, optionally filtered by status or client."""
    projects = _list(status=status, client=client)
    return json.dumps({"ok": True, "projects": projects, "count": len(projects)}, ensure_ascii=False, default=str)


def handle_project_update(project_id: str, **kwargs: Any) -> str:
    """Update project fields. Allowed: name, description, client, status."""
    allowed = {"name", "description", "client", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    proj = _update(project_id, **updates)
    if proj is None:
        return json.dumps({"ok": False, "error": f"Project '{project_id}' not found"})
    return json.dumps({"ok": True, "project": proj}, ensure_ascii=False, default=str)


def handle_project_delete(project_id: str) -> str:
    """Archive a project (soft delete — sets status to 'archived')."""
    result = _delete(project_id)
    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Tool schemas (OpenAI function-calling format)
# ---------------------------------------------------------------------------

PROJECT_CREATE_SCHEMA = {
    "name": "project_create",
    "description": "Create a new project. Projects group related tasks under a client or initiative.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Project name"},
            "description": {"type": "string", "description": "Optional project description"},
            "client": {"type": "string", "description": "Optional client or customer name"},
        },
        "required": ["name"],
    },
}

PROJECT_GET_SCHEMA = {
    "name": "project_get",
    "description": "Get full project details with task statistics (pending/in_progress/completed counts).",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string", "description": "Project ID"},
        },
        "required": ["project_id"],
    },
}

PROJECT_LIST_SCHEMA = {
    "name": "project_list",
    "description": "List all projects. Filter by status ('active'/'archived'/'completed') or client name.",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["active", "archived", "completed"], "description": "Filter by status"},
            "client": {"type": "string", "description": "Filter by client name"},
        },
    },
}

PROJECT_UPDATE_SCHEMA = {
    "name": "project_update",
    "description": "Update project fields: name, description, client, or status.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string", "description": "Project ID"},
            "name": {"type": "string", "description": "New name"},
            "description": {"type": "string", "description": "New description"},
            "client": {"type": "string", "description": "New client name"},
            "status": {"type": "string", "enum": ["active", "archived", "completed"], "description": "New status"},
        },
        "required": ["project_id"],
    },
}

PROJECT_DELETE_SCHEMA = {
    "name": "project_delete",
    "description": "Archive a project. Sets status to 'archived' and cancels all its pending tasks.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string", "description": "Project ID"},
        },
        "required": ["project_id"],
    },
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def check_requirements() -> bool:
    """No external dependencies — always available."""
    return True


for schema, handler in [
    (PROJECT_CREATE_SCHEMA, handle_project_create),
    (PROJECT_GET_SCHEMA, handle_project_get),
    (PROJECT_LIST_SCHEMA, handle_project_list),
    (PROJECT_UPDATE_SCHEMA, handle_project_update),
    (PROJECT_DELETE_SCHEMA, handle_project_delete),
]:
    registry.register(
        name=schema["name"],
        toolset="orchestra",
        schema=schema,
        handler=lambda args, name=schema["name"], h=handler: h(**args),
        check_fn=check_requirements,
        emoji="📁",
    )
