#!/usr/bin/env python3
"""Quick test for Hermes-Orchestra tools."""

import sys
import os

# Add tools dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

# Use temp dir for test
test_home = "/tmp/hermes-orchestra-test-db"
os.makedirs(test_home, exist_ok=True)
os.environ["HERMES_HOME"] = test_home

from project_store import (
    project_create, project_get, project_list, project_delete, project_stats,
    task_create, task_get, task_list, task_update, task_breakdown, task_assign, task_delete,
)

errors = 0

def check(name, ok, detail=""):
    global errors
    if ok:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        errors += 1

# --- Projects ---
print("=== Projects ===")
p1 = project_create("Test Project", description="Testing", client="TestClient")
check("project_create", p1["ok"])
pid = p1["project"]["id"]

p2 = project_get(pid)
check("project_get", p2 is not None and p2["name"] == "Test Project")

pl = project_list()
check("project_list", len(pl) >= 1)

ps = project_stats(pid)
check("project_stats", ps["total"] == 0)

# --- Tasks ---
print("\n=== Tasks ===")
t1 = task_create(pid, "Main task", description="Do the thing")
check("task_create", t1["ok"])
tid = t1["task"]["id"]

t2 = task_get(tid)
check("task_get", t2 is not None and t2["title"] == "Main task")

tl = task_list(project_id=pid)
check("task_list", len(tl) == 1)

# --- Task Update ---
t3 = task_update(tid, status="in_progress", priority="high")
check("task_update status/priority", t3 is not None and t3["status"] == "in_progress")

# --- Task Assign ---
t4 = task_assign(tid, "hermes")
check("task_assign", t4 is not None and t4["assignee"] == "hermes")

# --- Task Breakdown ---
br = task_breakdown(tid, [
    {"title": "Subtask A", "description": "First part"},
    {"title": "Subtask B", "description": "Second part"},
])
check("task_breakdown ok", br["ok"])
check("task_breakdown count", br["count"] == 2)

# Verify subtasks exist
subs = task_list(project_id=pid, parent_task_id=tid)
check("subtasks listed", len(subs) == 2)

# Parent should now be in_progress
parent = task_get(tid)
check("parent auto-progressed", parent["status"] == "in_progress")

# --- Task Delete ---
t5 = task_delete(subs[0]["id"])
check("task_delete", t5["ok"])

ps = project_stats(pid)
check("stats after delete", ps["cancelled"] == 1)

# --- Project Delete ---
pd = project_delete(pid)
check("project_delete", pd["ok"])

pp = project_get(pid)
check("project archived", pp is not None and pp["status"] == "archived")

# --- Summary ---
print(f"\n{'='*40}")
print(f"Total: {errors} failures")
sys.exit(1 if errors > 0 else 0)
