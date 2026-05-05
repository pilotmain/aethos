"""Skills: user JSON docs (Phase 22) + optional packaged manifests (Phase 53) + plugin runtime (Phase 6)."""

from app.services.skills.clawhub_client import ClawHubClient
from app.services.skills.clawhub_models import ClawHubSkillInfo
from app.services.skills.manifest_registry import SkillPackageRegistry
from app.services.skills.models import SkillMeta
from app.services.skills.plugin_registry import get_plugin_skill_registry
from app.services.skills.registry import list_skill_docs, save_skill_doc

__all__ = [
    "ClawHubClient",
    "ClawHubSkillInfo",
    "SkillMeta",
    "SkillPackageRegistry",
    "get_plugin_skill_registry",
    "list_skill_docs",
    "save_skill_doc",
]
