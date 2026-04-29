#!/usr/bin/env python3
"""
Task Management Tools for Hermes-Orchestra.

Provides persistent task CRUD, breakdown into subtasks, assignment,
and event logging. Auto-registers with the Hermes tool registry on import.
"""

import json
from typing import Any, Dict, List, Optional

from tools.project_store import (
    task_create as _create,
    task_get as _get,
    task_list as _list,
    task_update as _update,
    task_breakdown as _breakdown,
    task_assign as _assign,
    task_delete as _delete,
    task_event_add as _event_add,
    task_event_list as _event_list,
    project_get,
)
from tools.registry import registry, tool_error

# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def handle_task_create(
    project_id: str,
    title: str,
    description: str = "",
    parent_task_id: Optional[str] = None,
) -> str:
    """Create a task in a project (optionally as subtask)."""
    result = _create(project_id, title, description=description, parent_task_id=parent_task_id)
    return json.dumps(result, ensure_ascii=False, default=str)


def handle_task_get(task_id: str) -> str:
    """Get task details."""
    task = _get(task_id)
    if task is None:
        return json.dumps({"ok": False, "error": f"Task '{task_id}' not found"})
    events = _event_list(task_id, limit=10)
    task["recent_events"] = events
    return json.dumps({"ok": True, "task": task}, ensure_ascii=False, default=str)


def handle_task_list(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
) -> str:
    """List tasks, optionally filtered by project, status, or assignee."""
    tasks = _list(project_id=project_id, status=status, assignee=assignee)
    # Count by status
    counts = {}
    for t in tasks:
        s = t.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1
    return json.dumps({
        "ok": True,
        "tasks": tasks,
        "count": len(tasks),
        "summary": counts,
    }, ensure_ascii=False, default=str)


def handle_task_update(task_id: str, **kwargs: Any) -> str:
    """Update task fields. Allowed: title, description, status, assignee, priority, deadline."""
    allowed = {"title", "description", "status", "assignee", "priority", "deadline"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    task = _update(task_id, **updates)
    if task is None:
        return json.dumps({"ok": False, "error": f"Task '{task_id}' not found"})
    # Log the status change event
    if "status" in updates:
        _event_add(task_id, "status_change", f"Status changed to {updates['status']}")
    return json.dumps({"ok": True, "task": task}, ensure_ascii=False, default=str)


def handle_task_breakdown(
    parent_task_id: str,
    subtasks: List[Dict[str, str]],
) -> str:
    """Split a task into multiple subtasks atomically."""
    result = _breakdown(parent_task_id, subtasks)
    if result.get("ok"):
        _event_add(parent_task_id, "breakdown", f"Split into {len(subtasks)} subtasks")
    return json.dumps(result, ensure_ascii=False, default=str)


def handle_task_assign(task_id: str, assignee: str) -> str:
    """Assign a task to an agent type (e.g. 'hermes', 'codex', 'claude')."""
    task = _assign(task_id, assignee)
    if task is None:
        return json.dumps({"ok": False, "error": f"Task '{task_id}' not found"})
    _event_add(task_id, "assign", f"Assigned to {assignee}")
    return json.dumps({"ok": True, "task": task}, ensure_ascii=False, default=str)


def handle_task_delete(task_id: str) -> str:
    """Cancel a task (soft delete — sets status to 'cancelled')."""
    result = _delete(task_id)
    if result.get("ok"):
        _event_add(task_id, "cancelled", "Task cancelled")
    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TASK_CREATE_SCHEMA = {
    "name": "task_create",
    "description": "Create a task in a project. Optionally specify a parent_task_id to create a subtask.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string", "description": "Project ID to add the task to"},
            "title": {"type": "string", "description": "Task title"},
            "description": {"type": "string", "description": "Optional task description"},
            "parent_task_id": {"type": "string", "description": "Optional parent task ID for subtasking"},
        },
        "required": ["project_id", "title"],
    },
}

TASK_GET_SCHEMA = {
    "name": "task_get",
    "description": "Get task details with recent events.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task ID"},
        },
        "required": ["task_id"],
    },
}

TASK_LIST_SCHEMA = {
    "name": "task_list",
    "description": "List tasks. Filter by project_id, status ('pending'/'in_progress'/'completed'/'cancelled'/'blocked'), or assignee.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string", "description": "Filter by project"},
            "status": {"type": "string", "description": "Filter by status"},
            "assignee": {"type": "string", "description": "Filter by assignee"},
        },
    },
}

TASK_UPDATE_SCHEMA = {
    "name": "task_update",
    "description": "Update task: title, description, status, assignee, priority ('low'/'medium'/'high'/'critical'), or deadline (ISO timestamp).",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task ID"},
            "title": {"type": "string", "description": "New title"},
            "description": {"type": "string", "description": "New description"},
            "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "cancelled", "blocked"], "description": "New status"},
            "assignee": {"type": "string", "description": "Assignee (e.g. 'hermes', 'codex', 'claude')"},
            "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"], "description": "Priority level"},
            "deadline": {"type": "string", "description": "Deadline ISO timestamp"},
        },
        "required": ["task_id"],
    },
}

TASK_BREAKDOWN_SCHEMA = {
    "name": "task_breakdown",
    "description": "Split a task into multiple subtasks. Provide subtasks as an array of {title, description}. Parent task auto-set to in_progress.",
    "parameters": {
        "type": "object",
        "properties": {
            "parent_task_id": {"type": "string", "description": "Task to split"},
            "subtasks": {
                "type": "array",
                "description": "Array of subtask objects",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Subtask title"},
                        "description": {"type": "string", "description": "Optional description"},
                    },
                    "required": ["title"],
                },
            },
        },
        "required": ["parent_task_id", "subtasks"],
    },
}

TASK_ASSIGN_SCHEMA = {
    "name": "task_assign",
    "description": "Assign a task to a specific agent type. Use 'hermes' for delegate_task, 'codex'/'claude' for ACP agents, or any custom name.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task ID"},
            "assignee": {"type": "string", "description": "Agent type (hermes / codex / claude / openclaw / gemini)"},
        },
        "required": ["task_id", "assignee"],
    },
}

TASK_DELETE_SCHEMA = {
    "name": "task_delete",
    "description": "Cancel a task (soft delete — sets status to 'cancelled').",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task ID"},
        },
        "required": ["task_id"],
    },
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def check_requirements() -> bool:
    """No external dependencies — always available."""
    return True


for schema, handler in [
    (TASK_CREATE_SCHEMA, handle_task_create),
    (TASK_GET_SCHEMA, handle_task_get),
    (TASK_LIST_SCHEMA, handle_task_list),
    (TASK_UPDATE_SCHEMA, handle_task_update),
    (TASK_BREAKDOWN_SCHEMA, handle_task_breakdown),
    (TASK_ASSIGN_SCHEMA, handle_task_assign),
    (TASK_DELETE_SCHEMA, handle_task_delete),
]:
    registry.register(
        name=schema["name"],
        toolset="orchestra",
        schema=schema,
        handler=lambda args, name=schema["name"], h=handler: h(**args),
        check_fn=check_requirements,
        emoji="✅",
    )
