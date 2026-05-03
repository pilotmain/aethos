"""Host resource limits policy (Phase 54 MVP — validation + Mission Control exposure)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    max_cpu_percent: float | None
    max_memory_mb: int | None
    max_gpu_memory_mb: int | None
    max_parallel_tasks: int | None


def load_resource_policy() -> ResourcePolicy:
    s = get_settings()
    return ResourcePolicy(
        max_cpu_percent=float(getattr(s, "nexa_resource_max_cpu_percent", 0.0) or 0.0) or None,
        max_memory_mb=int(getattr(s, "nexa_resource_max_memory_mb", 0) or 0) or None,
        max_gpu_memory_mb=int(getattr(s, "nexa_resource_max_gpu_memory_mb", 0) or 0) or None,
        max_parallel_tasks=int(getattr(s, "nexa_resource_max_parallel_tasks", 0) or 0) or None,
    )


def policy_dict() -> dict[str, float | int | None]:
    p = load_resource_policy()
    return {
        "max_cpu_percent": p.max_cpu_percent,
        "max_memory_mb": p.max_memory_mb,
        "max_gpu_memory_mb": p.max_gpu_memory_mb,
        "max_parallel_tasks": p.max_parallel_tasks,
    }


__all__ = ["ResourcePolicy", "load_resource_policy", "policy_dict"]
