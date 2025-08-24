from supabase import create_client, Client
from typing import List, Dict, Optional
from config import SUPABASE_URL, SUPABASE_KEY


class SupabaseService:
    def __init__(self):
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def add_task(self, title: str, description: str = "") -> Dict:
        """Add a new task to the database"""
        task_data = {"title": title, "description": description, "done": False}

        result = self.supabase.table("tasks").insert(task_data).execute()

        if result.data:
            return result.data[0]
        else:
            raise Exception("Failed to add task")

    def complete_task(self, task_id: int) -> Dict:
        """Mark a task as completed"""
        result = (
            self.supabase.table("tasks")
            .update({"done": True})
            .eq("id", task_id)
            .execute()
        )

        if result.data:
            return result.data[0]
        else:
            raise Exception(f"Task {task_id} not found")

    def list_tasks(self) -> List[Dict]:
        """Get all tasks from the database"""
        result = self.supabase.table("tasks").select("*").order("id").execute()
        return result.data if result.data else []
