# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

# DO NOT MODIFY WITHOUT SECURITY REVIEW — payload immutability after firewall gate.

"""Frozen dict — blocks mutation after the privacy firewall prepares outbound payloads."""

from __future__ import annotations


class FrozenPayloadDict(dict):
    """Dict subclass that rejects writes (Phase 17 — prevent post-firewall mutation)."""

    _ERR = "CRITICAL: Payload mutation not allowed after privacy firewall gate"

    def __setitem__(self, key, value) -> None:  # type: ignore[override]
        raise RuntimeError(self._ERR)

    def __delitem__(self, key) -> None:  # type: ignore[override]
        raise RuntimeError(self._ERR)

    def update(self, *args, **kwargs) -> None:  # type: ignore[override]
        raise RuntimeError(self._ERR)

    def pop(self, *args, **kwargs):  # type: ignore[override]
        raise RuntimeError(self._ERR)

    def popitem(self):  # type: ignore[override]
        raise RuntimeError(self._ERR)

    def clear(self) -> None:  # type: ignore[override]
        raise RuntimeError(self._ERR)

    def setdefault(self, *args, **kwargs):  # type: ignore[override]
        raise RuntimeError(self._ERR)

    def __ior__(self, other):  # type: ignore[override]
        raise RuntimeError(self._ERR)


__all__ = ["FrozenPayloadDict"]
