"""Legacy REST prefix ``/api/v1/memory`` — removed (HTTP 410).

Agent memory (preferences, soul, notes) lives under ``/api/v1/web/memory/…``.
Persistent Nexa memory documents: ``/api/v1/nexa-memory``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/memory", tags=["memory"])

_DETAIL = (
    "Legacy endpoint removed. Use GET/POST /api/v1/nexa-memory for persistent memory documents; "
    "use /api/v1/web/memory/… for agent preferences, state, notes, soul, forget (authenticated web paths)."
)


def _gone() -> None:
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=_DETAIL)


@router.get("")
def memory_root_gone() -> None:
    _gone()


@router.put("/preferences")
def memory_preferences_gone() -> None:
    _gone()


@router.get("/state")
def memory_state_gone() -> None:
    _gone()


@router.post("/remember")
def memory_remember_gone() -> None:
    _gone()


@router.patch("/notes")
def memory_notes_patch_gone() -> None:
    _gone()


@router.post("/notes/delete")
def memory_notes_delete_gone() -> None:
    _gone()


@router.post("/forget")
def memory_forget_gone() -> None:
    _gone()


@router.put("/soul")
def memory_soul_gone() -> None:
    _gone()
