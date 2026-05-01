"""Tests for mission control graph_builder."""

from app.services.mission_control.graph_builder import build_graph


def test_build_graph_empty_state():
    out = build_graph({})
    assert out == {"nodes": [], "edges": []}


def test_build_graph_tasks_nodes_and_dependency_edges():
    state = {
        "tasks": [
            {
                "mission_id": "m1",
                "agent_handle": "a",
                "role": "Planner",
                "status": "completed",
                "depends_on": [],
            },
            {
                "mission_id": "m1",
                "agent_handle": "b",
                "role": "Worker",
                "status": "running",
                "depends_on": ["a"],
            },
        ]
    }
    out = build_graph(state)
    assert {n["id"] for n in out["nodes"]} == {"m1:a", "m1:b"}
    assert out["edges"] == [{"from": "m1:a", "to": "m1:b"}]


def test_build_graph_same_handle_different_missions():
    state = {
        "tasks": [
            {
                "mission_id": "m1",
                "agent_handle": "worker",
                "role": "A",
                "status": "queued",
                "depends_on": [],
            },
            {
                "mission_id": "m2",
                "agent_handle": "worker",
                "role": "B",
                "status": "queued",
                "depends_on": [],
            },
        ]
    }
    out = build_graph(state)
    ids = sorted(n["id"] for n in out["nodes"])
    assert ids == ["m1:worker", "m2:worker"]


def test_build_graph_tasks_without_mission_id_use_spawn_bucket():
    state = {
        "tasks": [
            {
                "id": 42,
                "spawn_group_id": "sg1",
                "agent_handle": "alpha",
                "role": "Lead",
                "status": "running",
                "depends_on": [],
            },
        ]
    }
    out = build_graph(state)
    assert out["nodes"][0]["id"] == "spawn:sg1:alpha"


def test_build_graph_legacy_missions_agents():
    state = {
        "missions": [
            {
                "id": "legacy-m",
                "agents": [
                    {"handle": "x", "role": "Lead", "status": "running", "depends_on": []},
                    {"handle": "y", "role": "Support", "status": "queued", "depends_on": ["x"]},
                ],
            }
        ]
    }
    out = build_graph(state)
    assert {n["id"] for n in out["nodes"]} == {"legacy-m:x", "legacy-m:y"}
    assert out["edges"] == [{"from": "legacy-m:x", "to": "legacy-m:y"}]
