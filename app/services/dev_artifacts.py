"""Per-job artifact directory under .runtime/dev_jobs/."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.services.handoff_paths import PROJECT_ROOT

RUNTIME_DEV_JOBS = Path(PROJECT_ROOT) / ".runtime" / "dev_jobs"


def job_artifact_dir(job_id: int) -> Path:
    return RUNTIME_DEV_JOBS / f"job_{job_id}"


def ensure_job_artifact_dir(job_id: int) -> Path:
    d = job_artifact_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def copy_task_to_artifacts(source_task: Path, artifact_dir: Path) -> Path | None:
    if not source_task.is_file():
        return None
    dest = artifact_dir / "task.md"
    try:
        shutil.copy2(source_task, dest)
    except OSError:
        return None
    return dest


def copy_review_to_artifacts(review_path: Path, artifact_dir: Path) -> Path | None:
    if not review_path.is_file():
        return None
    dest = artifact_dir / "review.md"
    try:
        shutil.copy2(review_path, dest)
    except OSError:
        return None
    return dest


def write_diff_artifacts(artifact_dir: Path, project_root: Path) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for name, args in (
        ("diff_stat.txt", ["git", "diff", "--stat"]),
        ("changed_files.txt", ["git", "diff", "--name-only"]),
    ):
        try:
            p = subprocess.run(
                args,
                cwd=str(project_root),
                text=True,
                capture_output=True,
                check=False,
            )
            t = (p.stdout or "") + (("\n" + p.stderr) if p.stderr else "")
            (artifact_dir / name).write_text(t[:1_000_000], encoding="utf-8")
        except OSError:
            (artifact_dir / name).write_text("error running git diff\n", encoding="utf-8")
