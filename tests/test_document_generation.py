"""Document generation: files, DB rows, API auth, safety."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.document_artifact import DocumentArtifactModel
from app.services import document_generation as dg
from app.services.document_export_intent import detect_natural_export_format
from app.services.document_template_intent import is_template_document_intent, parse_template_document_request


@pytest.fixture
def gen_base(tmp_path, monkeypatch):
    """Place runtime docs under tmp_path; align PROJECT_ROOT so relative paths in DB stay consistent."""
    base = tmp_path / "runtime" / "generated_documents"
    base.mkdir(parents=True)
    monkeypatch.setattr(dg, "get_generated_documents_base", lambda: base)
    monkeypatch.setattr(dg, "PROJECT_ROOT", tmp_path)
    return base


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_sanitize_file_stem():
    assert dg.sanitize_file_stem("Hello / World!") == "Hello_World"
    assert dg.sanitize_file_stem("") == "document"


def test_content_looks_sensitive():
    assert dg.content_looks_sensitive("here sk-123456789012345678901234567890")
    assert not dg.content_looks_sensitive("plain notes about APIs in general")


def test_build_smart_and_stem():
    t = dg.build_smart_export_title("# Nexa research summary\n\nBody here.\n", source_type="chat")
    assert "Nexa research" in t
    s = dg.export_stem_for_filename(t, "chat")
    assert "202" in s or "chat-export" in s


def test_generate_markdown_creates_file(gen_base, tmp_path, db_session):
    art = dg.generate_document(
        db_session,
        title="T1",
        body_markdown="# Hi\n\nBody.",
        format="md",
        user_id="u_docgen_1",
        source_type="chat",
    )
    assert art.id > 0
    assert Path(art.file_path).is_absolute() is False
    assert (tmp_path / art.file_path).is_file()
    row = db_session.get(DocumentArtifactModel, art.id)
    assert row and row.owner_user_id == "u_docgen_1"


def test_generate_txt(gen_base, db_session):
    art = dg.generate_document(
        db_session,
        title="Plain",
        body_markdown="Line one\nLine two",
        format="txt",
        user_id="u_docgen_2",
    )
    assert art.format == "txt"


def test_generate_docx_and_pdf(gen_base, tmp_path, db_session):
    body = "## Section\n\nParagraph with **bold**."
    d = dg.generate_document(
        db_session,
        title="W",
        body_markdown=body,
        format="docx",
        user_id="u_docgen_3",
    )
    assert d.format == "docx"
    assert (tmp_path / d.file_path).is_file()
    p = dg.generate_document(
        db_session,
        title="P",
        body_markdown=body,
        format="pdf",
        user_id="u_docgen_3",
    )
    assert p.format == "pdf"
    assert (tmp_path / p.file_path).is_file()


def test_sensitive_blocked(gen_base, db_session):
    with pytest.raises(dg.DocumentGenerationError) as ei:
        dg.generate_document(
            db_session,
            title="x",
            body_markdown="key sk-123456789012345678901234567890",
            format="md",
            user_id="u1",
        )
    assert ei.value.code == "sensitive_content"
    assert "sensitive" in str(ei.value).lower() and "did not export" in str(ei.value).lower()


def test_get_path_rejects_other_user(gen_base, db_session):
    a = dg.generate_document(
        db_session,
        title="Own",
        body_markdown="x",
        format="md",
        user_id="owner_only",
    )
    assert dg.get_document_path_for_owner(db_session, a.id, "owner_only") is not None
    assert dg.get_document_path_for_owner(db_session, a.id, "someone_else") is None


@patch("app.core.security.get_settings")
def test_web_generate_and_download(mock_gs, gen_base, db_session, tmp_path, monkeypatch):
    mock_gs.return_value = type(
        "S",
        (),
        {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"},
    )()
    monkeypatch.setattr(dg, "get_generated_documents_base", lambda: gen_base)
    c = TestClient(app)
    uid = "web_doc_unique"
    r = c.post(
        "/api/v1/web/documents/generate",
        json={
            "title": "API Test",
            "format": "md",
            "body_markdown": "# API\n\nok",
            "source_type": "chat",
        },
        headers={"X-User-Id": uid},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["format"] == "md"
    assert "download" in j["download_url"]
    d = c.get(
        f"/api/v1{j['download_url']}",
        headers={"X-User-Id": uid},
    )
    assert d.status_code == 200
    assert b"API" in d.content

    other = c.get(
        f"/api/v1{j['download_url']}",
        headers={"X-User-Id": "local_other_zzz"},
    )
    assert other.status_code == 404


def test_detect_natural_export_format():
    assert detect_natural_export_format("export this as a pdf") == "pdf"
    assert detect_natural_export_format("make a word document") in ("docx", "pdf")
    assert detect_natural_export_format("hi there") is None


def test_template_intent_project_plan():
    assert is_template_document_intent("Create a project plan PDF for my Nexa web UI work")
    req, body, cl = parse_template_document_request(
        "Create a project plan PDF for my Nexa web UI work",
        None,
    )
    assert cl is None
    assert req is not None and body is not None
    assert req.format == "pdf" and "Plan" in body
