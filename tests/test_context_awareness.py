# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 50 — infra and stack detection."""

from __future__ import annotations

from app.services.context_awareness import detect_infra_context, detect_stack_tags


def test_detect_infra_oidc_eks() -> None:
    t = "OIDC callback fails on EKS with invalid redirect"
    tags = detect_infra_context(t)
    assert any("OIDC" in x for x in tags)
    assert any("Kubernetes" in x or "EKS" in x for x in tags)


def test_detect_stack_typescript_python() -> None:
    t = "pytest and mypy pass but npm run build fails in App.tsx"
    s = detect_stack_tags(t)
    assert "TypeScript" in s
    assert "Python" in s
