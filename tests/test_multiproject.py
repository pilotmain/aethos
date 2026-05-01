from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.project import Project
from app.services.project_parser import parse_dev_project_phrase, parse_ops_project_scopes
from app.services.ops.ops_project_context import resolve_ops_project


def test_parse_ops_project_scopes() -> None:
    s = parse_ops_project_scopes(
        "logs nexa api",
        known_project_keys=["nexa", "foo"],
    )
    assert s.get("project_key") == "nexa"
    assert s.get("service") == "api"


def test_parse_dev_in_clause() -> None:
    k, t = parse_dev_project_phrase("fix tests in client-dashboard", known_project_keys=["client-dashboard"])
    assert k == "client-dashboard"
    assert "fix tests" in t


def test_resolve_ops_explicit_missing_project() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Session = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(bind=engine, tables=[Project.__table__])
    db = Session()
    err = resolve_ops_project(
        db, {"project_key": "nope", "project_key_explicit": True},
        active_project_key=None,
    )[1]
    assert err and "unknown project" in err.lower()
    db.close()
    engine.dispose()


def test_local_docker_import() -> None:
    from app.services.ops.providers.local_docker import LocalDockerProvider

    assert LocalDockerProvider().key == "local_docker"
