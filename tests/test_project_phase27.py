# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 27 — Mission Control projects, tasks, checkout, mission tree."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.project.controller import ProjectController
from app.services.project.models import ProjectStatus, TaskStatus
from app.services.project.persistence import (
    MissionControlStateStore,
    ProjectStore,
    TaskStore,
)
from app.services.sub_agent_registry import AgentRegistry
from app.services.team.roster import TeamRoster


class _S:
    def __init__(self) -> None:
        self.nexa_agent_orchestration_enabled = False
        self.nexa_task_lock_timeout_seconds = 3600


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "mission.db"


@pytest.fixture
def controller(db_path: Path) -> ProjectController:
    AgentRegistry.reset()
    return ProjectController(
        project_store=ProjectStore(db_path),
        task_store=TaskStore(db_path),
        state_store=MissionControlStateStore(db_path),
        team_roster=TeamRoster(),
    )


@patch("app.services.project.controller.get_settings", return_value=_S())
def test_create_project_and_task(_, controller: ProjectController) -> None:
    p = controller.create_project("Shop", "Build a store", team_scope="chat1")
    assert p.team_scope == "chat1"
    assert controller.get_current_project_id("chat1") == p.id

    t = controller.add_task("DB schema", project_id=p.id)
    assert t.project_id == p.id
    tasks = controller.list_tasks(project_id=p.id)
    assert len(tasks) == 1


@patch("app.services.project.controller.get_settings", return_value=_S())
def test_complete_all_tasks_completes_project(_, controller: ProjectController) -> None:
    p = controller.create_project("X", "goal", team_scope="c2")
    t = controller.add_task("Only task", project_id=p.id)
    assert controller.complete_task(t.id, "user-a")
    proj = controller.get_project(p.id)
    assert proj is not None
    assert proj.status == ProjectStatus.COMPLETED


@patch("app.services.project.controller.get_settings", return_value=_S())
def test_claim_and_unclaim(_, controller: ProjectController) -> None:
    p = controller.create_project("P", "g", team_scope="c3")
    t = controller.add_task("Work", project_id=p.id)
    assert controller.claim_task(t.id, "alice")
    t2 = controller.get_task(t.id)
    assert t2 is not None
    assert t2.status == TaskStatus.IN_PROGRESS
    assert t2.locked_by == "alice"
    assert controller.unclaim_task(t.id, "alice")
    t3 = controller.get_task(t.id)
    assert t3 is not None
    assert t3.status == TaskStatus.PENDING


@patch("app.services.project.controller.get_settings", return_value=_S())
def test_update_task_status(_, controller: ProjectController) -> None:
    p = controller.create_project("P", "g", team_scope="c6")
    t = controller.add_task("T", project_id=p.id)
    assert controller.update_task_status(t.id, TaskStatus.IN_PROGRESS, "c6") is True
    assert controller.get_task(t.id).status == TaskStatus.IN_PROGRESS  # type: ignore[union-attr]
    assert controller.update_task_status("badid", TaskStatus.DONE, "c6") is False


@patch("app.services.project.controller.get_settings", return_value=_S())
def test_mission_tree(_, controller: ProjectController) -> None:
    p = controller.create_project("Big", "Because revenue", team_scope="c4")
    controller.add_task("A", project_id=p.id)
    controller.add_task("B", project_id=p.id)
    tree = controller.build_mission_tree(p.id)
    assert tree["tasks"]["total"] == 2
    assert len(tree["tasks"]["items"]) == 2
    assert "why_this_matters" in tree


@patch("app.services.project.controller.get_settings", return_value=_S())
def test_assign_requires_member_when_orchestration_on(_, controller: ProjectController) -> None:
    orch = _S()
    orch.nexa_agent_orchestration_enabled = True
    with patch("app.services.project.controller.get_settings", return_value=orch):
        ctrl = ProjectController(
            project_store=controller.project_store,
            task_store=controller.task_store,
            state_store=controller.state_store,
            team_roster=controller.team_roster,
        )
        p = ctrl.create_project("Q", "g", team_scope="c5")
        t = ctrl.add_task("T", project_id=p.id)
        assert ctrl.assign_task(t.id, "missing-agent", "x") is False
