"""
Open-core enterprise feature gates (self-hosted).

OSS builds stay unlocked by default. Enterprise identifiers can be enabled via:

- Verified commercial license (Ed25519 ``nexa_lic_v1.*`` token + PEM); see :mod:`app.services.licensing`.
- ``NEXA_ENTERPRISE_GRANTED_FEATURES`` — comma-separated entitlement list for pilots / contracts.
- Optional dev unlock when ``app_env`` is development and ``nexa_open_core_dev_unlock`` is true.

Use :func:`is_enterprise_feature_enabled` from API routes and services; keep ``nexa_enforce_enterprise_gates``
false until you intentionally turn on hard blocks.
"""

from __future__ import annotations

from app.core.config import get_settings

# Stable product keys (docs / sales) → license payload ``features`` IDs (see ``app.services.licensing.features``).
ENTERPRISE_FEATURES: dict[str, str] = {
    "rbac_multi_tenant": "rbac_organizations",
    "audit_logs": "audit_logs_advanced",
    "sso_integration": "sso_saml_oidc",
    "sla_monitoring": "sla_monitoring",
    "advanced_analytics": "analytics_advanced",
    "custom_integrations": "custom_webhooks",
    "priority_queue": "priority_queue",
    "unlimited_agents": "agents_unlimited",
}


def _granted_via_env(feature_key: str) -> bool:
    s = get_settings()
    raw = (getattr(s, "nexa_enterprise_granted_features", None) or "").strip()
    if not raw:
        return False
    want = {x.strip().lower() for x in raw.split(",") if x.strip()}
    fk = (feature_key or "").strip().lower()
    lic_id = ENTERPRISE_FEATURES.get(fk, fk).lower()
    return fk in want or lic_id in want


def _dev_unlock() -> bool:
    s = get_settings()
    if not bool(getattr(s, "nexa_open_core_dev_unlock", False)):
        return False
    env = (getattr(s, "app_env", "") or "").strip().lower()
    return env in ("development", "dev", "local")


def is_enterprise_feature_enabled(feature_key: str, user_id: str | None = None) -> bool:
    """
    Return True if an enterprise-only capability should be available.

    Non-enterprise keys (anything not listed in ``ENTERPRISE_FEATURES``) always return True.
    """
    fk = (feature_key or "").strip().lower()
    if fk not in ENTERPRISE_FEATURES:
        return True

    if _dev_unlock():
        return True
    if _granted_via_env(fk):
        return True

    from app.services.licensing.features import has_pro_feature

    lic_id = ENTERPRISE_FEATURES[fk]
    if has_pro_feature(lic_id):
        return True

    _ = user_id  # reserved for future per-user sponsor / billing hooks
    return False


# Back-compat alias for docs that reference ``FeatureFlags.is_enabled``.
class FeatureFlags:
    ENTERPRISE_FEATURES = ENTERPRISE_FEATURES

    @classmethod
    def is_enabled(cls, feature_name: str, user_id: str | None = None) -> bool:
        return is_enterprise_feature_enabled(feature_name, user_id=user_id)


__all__ = [
    "ENTERPRISE_FEATURES",
    "FeatureFlags",
    "is_enterprise_feature_enabled",
]
