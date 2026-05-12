# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Credential references — never embed raw secrets in API payloads."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SecretRef:
    name: str
    scope: str
    key_id: str
    """Opaque handle; not the secret value."""


__all__ = ["SecretRef"]
