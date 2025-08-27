from fastmcp import FastMCP
from typing import List, Dict
from supabase_service import SupabaseService
from fastmcp.server.http import Route, create_streamable_http_app
from starlette.responses import JSONResponse
import os

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
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    if os.getenv("PORT") or os.getenv("HOST"):
        # Build HTTP ASGI app with a health endpoint
        def health(_request):
            return JSONResponse({"status": "ok"})

        app = create_streamable_http_app(
            server=mcp,
            streamable_http_path="/mcp",
            routes=[Route("/health", health, methods=["GET"])],
        )

        import uvicorn

        uvicorn.run(app, host=host, port=port)
    else:
        # Running locally - use stdio transport
        mcp.run()
