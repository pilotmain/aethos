"""License status and validation (Ed25519 ``nexa_lic_v1`` tokens — see app/services/licensing)."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.feature_flags import ENTERPRISE_FEATURES, is_enterprise_feature_enabled
from app.services.licensing.features import licensed_feature_ids
from app.services.licensing.verify import verify_license_token

router = APIRouter(prefix="/license", tags=["license"])


class LicenseValidateRequest(BaseModel):
    license_key: str = Field(..., min_length=8, description="Full nexa_lic_v1.* token")


class LicenseValidateResponse(BaseModel):
    valid: bool
    features: list[str]
    expires_at: float | None = None
    message: str


@router.get("/status")
def license_status() -> dict[str, Any]:
    """Summarize configured license / env grants (no secret payload exposed)."""
    s = get_settings()
    pem = (getattr(s, "nexa_license_public_key_pem", None) or "").strip()
    lic_ids = sorted(licensed_feature_ids())
    ent_keys = [k for k in ENTERPRISE_FEATURES if is_enterprise_feature_enabled(k)]
    tier = "enterprise" if (lic_ids or ent_keys) else "community"
    return {
        "tier": tier,
        "has_verified_license_payload": bool(lic_ids),
        "licensed_feature_ids": lic_ids,
        "enterprise_capability_keys_enabled": ent_keys,
        "public_key_configured": bool(pem),
    }


@router.post("/validate", response_model=LicenseValidateResponse)
def validate_license(body: LicenseValidateRequest) -> LicenseValidateResponse:
    """Verify an arbitrary license string using the configured Ed25519 public key."""
    s = get_settings()
    pem = (getattr(s, "nexa_license_public_key_pem", None) or "").strip()
    if not pem:
        return LicenseValidateResponse(
            valid=False,
            features=[],
            message="License verification disabled (no NEXA_LICENSE_PUBLIC_KEY_PEM configured).",
        )
    payload = verify_license_token(body.license_key.strip(), public_key_pem=pem)
    if not payload:
        return LicenseValidateResponse(valid=False, features=[], message="Invalid or unsigned license token.")
    feats = payload.get("features")
    feat_list = [str(x).strip() for x in feats] if isinstance(feats, list) else []
    exp = payload.get("exp")
    exp_f: float | None = None
    if exp is not None:
        try:
            exp_f = float(exp)
            if exp_f < time.time():
                return LicenseValidateResponse(
                    valid=False,
                    features=feat_list,
                    expires_at=exp_f,
                    message="License expired.",
                )
        except (TypeError, ValueError):
            pass
    return LicenseValidateResponse(
        valid=True,
        features=feat_list,
        expires_at=exp_f,
        message="License signature valid.",
    )


__all__ = ["router"]
