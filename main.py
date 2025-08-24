from fastmcp import FastMCP
from typing import List, Dict
from supabase_service import SupabaseService

mcp = FastMCP("task-manager")

supabase_service = SupabaseService()


@mcp.tool()
def add_task(title: str, description: str = "") -> str:
    try:
        task = supabase_service.add_task(title, description)
        return f"Task {task['id']} added: {title}"
    except Exception as e:
        return f"Failed to add task: {str(e)}"


@mcp.tool()
def complete_task(task_id: int) -> str:
    try:
        task = supabase_service.complete_task(task_id)
        return f"Task {task_id} marked as done!"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def list_tasks() -> List[Dict]:
    try:
        return supabase_service.list_tasks()
    except Exception as e:
        return [{"error": f"Failed to fetch tasks: {str(e)}"}]


if __name__ == "__main__":
    mcp.run()
