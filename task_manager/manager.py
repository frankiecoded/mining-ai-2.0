import uuid
import time
import logging
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from pydantic import BaseModel, Field
from dataclasses import dataclass, field

logger = logging.getLogger("ai_os.task_manager")


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    GEOLOGICAL = "geological"
    EQUIPMENT = "equipment"
    SAFETY = "safety"
    FINANCIAL = "financial"
    MARKET = "market"
    DOCUMENT = "document"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    COORDINATION = "coordination"


class TaskProgress(BaseModel):
    step: str = ""
    total_steps: int = 0
    current_step: int = 0
    percentage: float = 0.0
    last_activity: str = ""
    recent_activities: List[str] = Field(default_factory=list)
    tool_uses: int = 0
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def update(self, step: str, current: int = 0, total: int = 0, activity: str = ""):
        self.step = step
        if total > 0:
            self.total_steps = total
        if current > 0:
            self.current_step = current
        if self.total_steps > 0:
            self.percentage = (self.current_step / self.total_steps) * 100
        if activity:
            self.last_activity = activity
            self.recent_activities.append(activity)
            if len(self.recent_activities) > 10:
                self.recent_activities = self.recent_activities[-10:]
        self.updated_at = datetime.utcnow()
        self.tool_uses += 1


class Task(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    title: str
    description: str = ""
    task_type: TaskType = TaskType.ANALYSIS
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    parent_id: Optional[str] = None
    assigned_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    progress: TaskProgress = Field(default_factory=TaskProgress)
    dependencies: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    subtasks: List[str] = Field(default_factory=list)

    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return None

    def is_active(self) -> bool:
        return self.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

    def summary(self) -> str:
        duration = self.duration_seconds()
        dur_str = f" ({duration:.1f}s)" if duration else ""
        progress_str = f" [{self.progress.percentage:.0f}%]" if self.progress.total_steps > 0 else ""
        return f"[{self.status.value.upper()}] {self.title}{dur_str}{progress_str}"


class TaskManager:
    """
    Task management system with background execution, progress tracking,
    stall detection, and parallel task support. Inspired by Claude Code's
    task system with coordinator pattern.

    Features:
      - Create, update, complete, cancel tasks
      - Track progress with step counting
      - Detect stalled tasks (no activity for N seconds)
      - Background task execution with callbacks
      - Parent-child task relationships
      - Parallel task execution support
    """

    STALL_TIMEOUT_SECONDS = 300  # 5 minutes no activity = stalled
    MAX_CONCURRENT_TASKS = 6
    MAX_TASK_HISTORY = 100

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._task_history: List[Task] = []
        self._running_tasks: Dict[str, Any] = {}  # task_id -> async task/future
        self._callbacks: Dict[str, List[Callable]] = {}
        self._stall_check_interval = 30

    def create_task(self, title: str, description: str = "", task_type: TaskType = TaskType.ANALYSIS,
                    priority: TaskPriority = TaskPriority.MEDIUM, parent_id: Optional[str] = None,
                    dependencies: Optional[List[str]] = None, tags: Optional[List[str]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> Task:
        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            parent_id=parent_id,
            dependencies=dependencies or [],
            tags=tags or [],
            metadata=metadata or {}
        )
        self._tasks[task.id] = task
        if parent_id and parent_id in self._tasks:
            self._tasks[parent_id].subtasks.append(task.id)
        logger.info(f"Created task: {task.summary()}")
        self._emit("created", task)
        return task

    def start_task(self, task_id: str) -> Optional[Task]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        if task.dependencies:
            for dep_id in task.dependencies:
                dep = self._tasks.get(dep_id)
                if dep and dep.status != TaskStatus.COMPLETED:
                    task.status = TaskStatus.BLOCKED
                    logger.info(f"Task {task_id} blocked by {dep_id}")
                    return task
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.progress.started_at = datetime.utcnow()
        task.progress.updated_at = datetime.utcnow()
        logger.info(f"Started task: {task.summary()}")
        self._emit("started", task)
        return task

    def update_progress(self, task_id: str, step: str = "", current: int = 0,
                        total: int = 0, activity: str = "") -> Optional[Task]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.progress.update(step, current, total, activity)
        self._emit("progress", task)
        return task

    def complete_task(self, task_id: str, result: str = "") -> Optional[Task]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.result = result
        logger.info(f"Completed task: {task.summary()}")
        self._emit("completed", task)
        self._check_dependents(task_id)
        return task

    def fail_task(self, task_id: str, error: str = "") -> Optional[Task]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        task.error = error
        logger.error(f"Failed task: {task.summary()} - {error}")
        self._emit("failed", task)
        return task

    def cancel_task(self, task_id: str) -> Optional[Task]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()
        logger.info(f"Cancelled task: {task.summary()}")
        self._emit("cancelled", task)
        if task_id in self._running_tasks:
            async_task = self._running_tasks.pop(task_id)
            if hasattr(async_task, 'cancel'):
                async_task.cancel()
        for sub_id in task.subtasks:
            self.cancel_task(sub_id)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None, task_type: Optional[TaskType] = None,
                   parent_id: Optional[str] = None, limit: int = 50) -> List[Task]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        if parent_id:
            tasks = [t for t in tasks if t.parent_id == parent_id]
        tasks.sort(key=lambda t: (-t.priority.value.__len__(), t.created_at))
        return tasks[:limit]

    def active_tasks(self) -> List[Task]:
        return self.list_tasks(status=TaskStatus.RUNNING) + self.list_tasks(status=TaskStatus.PENDING)

    def task_summary(self) -> Dict[str, Any]:
        all_tasks = list(self._tasks.values())
        active = [t for t in all_tasks if t.is_active()]
        completed = [t for t in all_tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in all_tasks if t.status == TaskStatus.FAILED]
        return {
            "total": len(all_tasks),
            "active": len(active),
            "completed": len(completed),
            "failed": len(failed),
            "by_type": {t.value: len([x for x in all_tasks if x.task_type == t]) for t in TaskType},
            "active_details": [t.summary() for t in active],
        }

    def detect_stalled_tasks(self) -> List[Task]:
        stalled = []
        now = datetime.utcnow()
        for task in self.active_tasks():
            if task.status == TaskStatus.RUNNING and task.progress.updated_at:
                idle_seconds = (now - task.progress.updated_at).total_seconds()
                if idle_seconds > self.STALL_TIMEOUT_SECONDS:
                    stalled.append(task)
                    logger.warning(f"Stalled task detected: {task.summary()} (idle {idle_seconds:.0f}s)")
        return stalled

    def _check_dependents(self, completed_id: str):
        for task in self._tasks.values():
            if task.status == TaskStatus.BLOCKED and completed_id in task.dependencies:
                all_met = all(
                    self._tasks.get(dep_id, Task(status=TaskStatus.PENDING)).status == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                )
                if all_met:
                    task.status = TaskStatus.PENDING
                    logger.info(f"Task {task.id} unblocked (dependency {completed_id} completed)")

    def _emit(self, event: str, task: Task):
        for callback in self._callbacks.get(event, []):
            try:
                callback(task)
            except Exception as e:
                logger.error(f"Task event callback error: {e}")

    def on(self, event: str, callback: Callable):
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def create_analysis_plan(self, query: str) -> List[Task]:
        tasks = []
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["geology", "ore", "grade", "drill", "assay", "soil", "exploration"]):
            tasks.append(self.create_task(
                title="Geological Analysis",
                description=f"Analyze geological data for: {query}",
                task_type=TaskType.GEOLOGICAL,
                priority=TaskPriority.HIGH
            ))
        if any(kw in query_lower for kw in ["equipment", "truck", "mill", "crusher", "status", "maintenance"]):
            tasks.append(self.create_task(
                title="Equipment Status Check",
                description=f"Check equipment status for: {query}",
                task_type=TaskType.EQUIPMENT,
                priority=TaskPriority.MEDIUM
            ))
        if any(kw in query_lower for kw in ["safety", "incident", "hazard", "ppe", "compliance", "msah"]):
            tasks.append(self.create_task(
                title="Safety Compliance Review",
                description=f"Review safety data for: {query}",
                task_type=TaskType.SAFETY,
                priority=TaskPriority.CRITICAL
            ))
        if any(kw in query_lower for kw in ["budget", "cost", "payroll", "procurement", "finance", "spend"]):
            tasks.append(self.create_task(
                title="Financial Analysis",
                description=f"Analyze financial data for: {query}",
                task_type=TaskType.FINANCIAL,
                priority=TaskPriority.MEDIUM
            ))
        if any(kw in query_lower for kw in ["price", "market", "gold", "commodity", "tanzanite", "diamond"]):
            tasks.append(self.create_task(
                title="Market Intelligence",
                description=f"Gather market data for: {query}",
                task_type=TaskType.MARKET,
                priority=TaskPriority.MEDIUM
            ))
        if not tasks:
            tasks.append(self.create_task(
                title="General Analysis",
                description=f"Analyze: {query}",
                task_type=TaskType.ANALYSIS,
                priority=TaskPriority.MEDIUM
            ))
        return tasks
