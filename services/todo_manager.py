import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_os.todo_manager")


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TodoPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TodoItem(BaseModel):
    id: str = Field(default_factory=lambda: f"todo_{uuid.uuid4().hex[:8]}")
    content: str
    status: TodoStatus = TodoStatus.PENDING
    priority: TodoPriority = TodoPriority.MEDIUM
    category: str = "general"
    assignee: str = ""
    due_date: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    notes: str = ""
    tags: List[str] = Field(default_factory=list)


class TodoManager:
    """
    Todo/task list management system adapted from Claude Code's TodoWriteTool.
    Manages shift task lists, safety checklists, and operational workflows.

    Features:
    - Create, update, complete, cancel tasks
    - Priority-based ordering
    - Category filtering (safety, maintenance, geological, financial)
    - Shift-based task management
    - Safety checklist templates
    """

    SAFETY_CHECKLIST = [
        {"content": "PPE check - hard hat, high-vis, steel toes, gloves", "priority": "critical", "category": "safety"},
        {"content": "Gas monitoring - O2, LEL, CO, H2S levels", "priority": "critical", "category": "safety"},
        {"content": "Equipment pre-start inspection", "priority": "high", "category": "safety"},
        {"content": "Emergency communication check", "priority": "high", "category": "safety"},
        {"content": "Ground conditions assessment", "priority": "high", "category": "safety"},
        {"content": "Weather conditions review", "priority": "medium", "category": "safety"},
        {"content": "Shift handover notes review", "priority": "medium", "category": "safety"},
    ]

    def __init__(self):
        self._todos: Dict[str, List[TodoItem]] = {}

    def _get_session_todos(self, session_id: str) -> List[TodoItem]:
        if session_id not in self._todos:
            self._todos[session_id] = []
        return self._todos[session_id]

    def add_todo(self, session_id: str, content: str, priority: str = "medium",
                category: str = "general", assignee: str = "", due_date: str = None,
                tags: List[str] = None) -> TodoItem:
        todos = self._get_session_todos(session_id)
        try:
            p = TodoPriority(priority)
        except ValueError:
            p = TodoPriority.MEDIUM
        todo = TodoItem(
            content=content,
            priority=p,
            category=category,
            assignee=assignee,
            due_date=due_date,
            tags=tags or [],
        )
        todos.append(todo)
        logger.info(f"Added todo: {todo.id} - {content}")
        return todo

    def update_todo(self, session_id: str, todo_id: str, status: str = None,
                   priority: str = None, content: str = None, notes: str = None) -> Optional[TodoItem]:
        todos = self._get_session_todos(session_id)
        for todo in todos:
            if todo.id == todo_id:
                if status:
                    try:
                        todo.status = TodoStatus(status)
                        if todo.status == TodoStatus.COMPLETED:
                            todo.completed_at = datetime.utcnow()
                    except ValueError:
                        pass
                if priority:
                    try:
                        todo.priority = TodoPriority(priority)
                    except ValueError:
                        pass
                if content:
                    todo.content = content
                if notes:
                    todo.notes = notes
                return todo
        return None

    def complete_todo(self, session_id: str, todo_id: str) -> Optional[TodoItem]:
        return self.update_todo(session_id, todo_id, status="completed")

    def remove_todo(self, session_id: str, todo_id: str) -> bool:
        todos = self._get_session_todos(session_id)
        before = len(todos)
        self._todos[session_id] = [t for t in todos if t.id != todo_id]
        return len(self._todos[session_id]) < before

    def list_todos(self, session_id: str, status: str = None, category: str = None) -> List[TodoItem]:
        todos = self._get_session_todos(session_id)
        if status:
            try:
                s = TodoStatus(status)
                todos = [t for t in todos if t.status == s]
            except ValueError:
                pass
        if category:
            todos = [t for t in todos if t.category == category]
        priority_order = {TodoPriority.CRITICAL: 0, TodoPriority.HIGH: 1, TodoPriority.MEDIUM: 2, TodoPriority.LOW: 3}
        return sorted(todos, key=lambda t: (priority_order.get(t.priority, 4), t.created_at))

    def get_safety_checklist(self, session_id: str) -> List[TodoItem]:
        todos = self._get_session_todos(session_id)
        existing_contents = {t.content for t in todos if t.category == "safety"}
        new_todos = []
        for item in self.SAFETY_CHECKLIST:
            if item["content"] not in existing_contents:
                todo = self.add_todo(
                    session_id, item["content"],
                    priority=item["priority"],
                    category="safety",
                    tags=["safety_checklist"]
                )
                new_todos.append(todo)
        return self.list_todos(session_id, category="safety")

    def render_todos(self, session_id: str) -> str:
        todos = self.list_todos(session_id)
        if not todos:
            return "No tasks in the list."
        status_icons = {
            TodoStatus.PENDING: "⬜",
            TodoStatus.IN_PROGRESS: "🔵",
            TodoStatus.COMPLETED: "✅",
            TodoStatus.BLOCKED: "🔴",
            TodoStatus.CANCELLED: "⏭️",
        }
        priority_icons = {
            TodoPriority.CRITICAL: "🚨",
            TodoPriority.HIGH: "⬆️",
            TodoPriority.MEDIUM: "➡️",
            TodoPriority.LOW: "⬇️",
        }
        categories = {}
        for todo in todos:
            cat = todo.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(todo)
        lines = ["## Task List", ""]
        for cat, cat_todos in categories.items():
            lines.append(f"### {cat.title()}")
            for todo in cat_todos:
                icon = status_icons.get(todo.status, "❓")
                pri = priority_icons.get(todo.priority, "")
                assignee = f" → {todo.assignee}" if todo.assignee else ""
                due = f" (due: {todo.due_date})" if todo.due_date else ""
                lines.append(f"{icon} {pri} {todo.content}{assignee}{due}")
                if todo.notes:
                    lines.append(f"   📝 {todo.notes}")
            lines.append("")
        completed = sum(1 for t in todos if t.status == TodoStatus.COMPLETED)
        total = len(todos)
        lines.append(f"**Progress:** {completed}/{total} completed ({completed/total*100:.0f}%)" if total > 0 else "")
        return "\n".join(lines)

    def todo_summary(self, session_id: str) -> Dict[str, Any]:
        todos = self._get_session_todos(session_id)
        return {
            "total": len(todos),
            "pending": sum(1 for t in todos if t.status == TodoStatus.PENDING),
            "in_progress": sum(1 for t in todos if t.status == TodoStatus.IN_PROGRESS),
            "completed": sum(1 for t in todos if t.status == TodoStatus.COMPLETED),
            "blocked": sum(1 for t in todos if t.status == TodoStatus.BLOCKED),
            "by_priority": {
                "critical": sum(1 for t in todos if t.priority == TodoPriority.CRITICAL),
                "high": sum(1 for t in todos if t.priority == TodoPriority.HIGH),
                "medium": sum(1 for t in todos if t.priority == TodoPriority.MEDIUM),
                "low": sum(1 for t in todos if t.priority == TodoPriority.LOW),
            },
        }
