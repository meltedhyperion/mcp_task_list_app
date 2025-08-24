from fastmcp import FastMCP
from typing import List, Dict

mcp = FastMCP("task-manager")

tasks: List[Dict] = []


@mcp.tool()
def add_task(title: str, description: str = "") -> str:
    task_id = len(tasks) + 1
    tasks.append(
        {"id": task_id, "title": title, "description": description, "done": False}
    )
    return f"✅ Task {task_id} added: {title}"


@mcp.tool()
def complete_task(task_id: int) -> str:
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            return f"🎉 Task {task_id} marked as done!"
    return f"⚠️ Task {task_id} not found."


@mcp.tool()
def list_tasks() -> List[Dict]:
    return tasks


if __name__ == "__main__":
    mcp.run()
