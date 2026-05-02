"""Autonomy and background planning (Phase 43–45)."""

from app.services.autonomy.decision import autonomous_decision_loop
from app.services.autonomy.efficiency import compress_context
from app.services.autonomy.executor import (
    execute_autonomous_tasks,
    get_pending_tasks,
    run_autonomy_executor_for_all_pending_users,
)
from app.services.autonomy.feedback import record_task_feedback
from app.services.autonomy.intelligence import build_intelligent_context, update_memory_weights
from app.services.autonomy.planner import autonomous_planner
from app.services.autonomy.prioritize import prioritize_tasks
from app.services.autonomy.rate_control import autonomy_rate_control
from app.services.autonomy.safety import should_execute

__all__ = [
    "autonomous_decision_loop",
    "autonomy_rate_control",
    "autonomous_planner",
    "build_intelligent_context",
    "compress_context",
    "execute_autonomous_tasks",
    "get_pending_tasks",
    "prioritize_tasks",
    "record_task_feedback",
    "run_autonomy_executor_for_all_pending_users",
    "should_execute",
    "update_memory_weights",
]
