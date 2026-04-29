---
name: hermes-orchestra
description: Persistent project/task management inside Hermes. Create projects, break down tasks, assign to agents, and track status — all in SQLite, cross-session.
version: 1.0.0
author: Nikolay Gusev
tags: [orchestra, project-management, multi-agent, orchestration]
---

# Hermes-Orchestra Skill

Persistent project and task management **inside Hermes**. No separate dashboard, no adapter contracts — just tools that create/read/update projects and tasks in SQLite, living forever across sessions.

## Use Cases

- **Multi-agent orchestration**: Create a project, break into tasks, assign each to hermes/codex/claude, dispatch in parallel
- **Client project tracking**: One project per client, track all ongoing work, see stats
- **Recurring workflows**: Saved as skills, triggered via `project_create` + `task_breakdown`

## Tools

### Project Tools

| Tool | Description |
|------|-------------|
| `project_create(name, description, client)` | Create a new project |
| `project_get(project_id)` | Get project + task stats |
| `project_list(status, client)` | List projects with filters |
| `project_update(project_id, ...)` | Update name/description/status |
| `project_delete(project_id)` | Archive project (soft delete) |

### Task Tools

| Tool | Description |
|------|-------------|
| `task_create(project_id, title, description, parent_task_id)` | Create task (optionally as subtask) |
| `task_get(task_id)` | Get task + recent events |
| `task_list(project_id, status, assignee)` | List tasks with filters |
| `task_update(task_id, ...)` | Update status/assignee/priority/deadline |
| `task_breakdown(parent_task_id, subtasks[])` | Split task into subtasks atomically |
| `task_assign(task_id, assignee)` | Assign to agent type (hermes/codex/claude) |
| `task_delete(task_id)` | Cancel task (soft delete) |

## Workflow: Orchestrate a Project

```
1. project_create(name="Client Site Audit", client="Client A")
2. task_create(project_id="proj-...", title="Audit log analysis")
3. task_breakdown(task_id, subtasks=[
     {title: "Parse log format", description: "..."},
     {title: "Build report", description: "..."},
   ])
4. task_assign(subtask_1_id, assignee="hermes")
5. task_assign(subtask_2_id, assignee="codex")
   # The orchestrator dispatches each subtask to the assigned agent
6. task_update(task_id, status="completed")
```

## Storage

All data lives in `~/.hermes/state.db` — the same SQLite database Hermes already uses for sessions. Tables: `projects`, `tasks`, `task_events`. Persistent across sessions, survives context compression, survives `/reset`.

## Requirements

- Hermes Agent (any version with tool registry support)
- No external dependencies
- No API keys needed
