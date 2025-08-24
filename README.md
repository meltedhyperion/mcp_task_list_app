# MCP TASK LIST APP

## Features

- ✅ Add new tasks with title and description
- 🎯 Mark tasks as completed
- 📋 List all tasks

## Setup

### 1. Install Dependencies

```bash
uv sync
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```bash
SUPABASE_URL=your_supabase_project_url_here
SUPABASE_KEY=your_supabase_anon_key_here
```

### 3. Run the Application

```bash
uv run main.py
```

## Database Schema

The `tasks` table has the following structure:

- `id`: Auto-incrementing primary key
- `title`: Task title (required)
- `description`: Task description (optional)
- `done`: Completion status (boolean)
- `created_at`: Timestamp when task was created
- `updated_at`: Timestamp when task was last updated

## MCP Tools Available

- `add_task(title: str, description: str = "")`: Add a new task
- `complete_task(task_id: int)`: Mark a task as completed
- `list_tasks()`: Get all tasks
