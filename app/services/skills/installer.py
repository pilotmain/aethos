"""Phase 17 — install / update / remove ClawHub skill packages (ZIP → skill.yaml → registry).

Phase 75 extends this module with:

* cross-skill dependency resolution (via
  :mod:`app.services.skills.dependency_resolver`) executed *before* the host
  install so a partial install never leaves a half-registered head skill;
* persistence of ``available_version`` / ``update_checked_at`` / ``category``
  on the local ``installed.yaml`` rows so the update checker and Marketplace
  UI can read fresh state without hitting the registry on every render;
* a small ``mark_update_checked`` helper used by
  :mod:`app.services.skills.update_checker`.
"""

from __future__ import annotations

import io
import logging
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.core.config import REPO_ROOT, get_settings
from app.services.skills.clawhub_client import ClawHubClient
from app.services.skills.clawhub_models import (
    InstalledSkill,
    SkillSource,
    SkillStatus,
    row_to_installed_skill,
)
from app.services.skills.loader import load_skill_manifest
from app.services.skills.plugin_registry import get_plugin_skill_registry

logger = logging.getLogger(__name__)


class SkillInstaller:
    """Install, update, remove marketplace skills on disk + plugin registry + manifest."""

    def __init__(self, skills_root: Path | None = None) -> None:
        self.settings = get_settings()
        raw = (getattr(self.settings, "nexa_clawhub_skill_root", None) or "").strip()
        if skills_root is not None:
            base = Path(skills_root)
        elif raw:
            base = Path(raw).expanduser()
            if not base.is_absolute():
                base = (REPO_ROOT / base).resolve()
        else:
            base = REPO_ROOT / "data" / "skills"
        self.skills_root = base
        self.manifest_path = self.skills_root / "installed.yaml"
        self.client = ClawHubClient()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.skills_root.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.exists():
            self._save_manifest([])

    def _load_manifest(self) -> list[InstalledSkill]:
        if not self.manifest_path.exists():
            return []
        try:
            raw = yaml.safe_load(self.manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("installed.yaml unreadable: %s", exc)
            return []
        rows = raw if isinstance(raw, list) else []
        out: list[InstalledSkill] = []
        for row in rows:
            if isinstance(row, dict) and row.get("name"):
                try:
                    out.append(row_to_installed_skill(row))
                except Exception:  # noqa: BLE001
                    continue
        return out

    def _save_manifest(self, skills: list[InstalledSkill]) -> None:
        data = [s.to_row() for s in skills]
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    def _trusted_publishers_list(self) -> list[str]:
        raw = (getattr(self.settings, "nexa_clawhub_trusted_publishers", "") or "").strip()
        if not raw:
            return []
        return [x.strip().lower() for x in raw.split(",") if x.strip()]

    def is_trusted_publisher(self, publisher: str) -> bool:
        allow = self._trusted_publishers_list()
        if not allow:
            return True
        return (publisher or "").strip().lower() in allow

    async def install(self, name: str, version: str = "latest", *, force: bool = False) -> tuple[bool, str, str | None]:
        """Install skill from ClawHub. Returns (ok, message, registered_skill_name)."""
        if not getattr(self.settings, "nexa_clawhub_enabled", True):
            return False, "clawhub_disabled", None

        if getattr(self.settings, "nexa_clawhub_require_install_approval", False) and not force:
            return False, "install_requires_approval_force_false", None

        nm = (name or "").strip()
        if not nm:
            return False, "invalid_name", None

        installed = self._load_manifest()

        remote = await self.client.get_skill_info(nm)
        if not remote:
            return False, "remote_metadata_unavailable", None

        if any(s.name == remote.name for s in installed):
            return False, "already_installed", None

        if getattr(self.settings, "nexa_clawhub_require_signature", False) and not (remote.signature or "").strip():
            return False, "signature_required_missing", None

        if not self.is_trusted_publisher(remote.publisher):
            return False, "publisher_not_trusted", None

        # Phase 75 — resolve cross-skill deps before downloading the head, so
        # an unsatisfiable graph fails fast (no half-installed leaves). Pip
        # deps from ``manifest.dependencies`` are still handled below by the
        # plugin registry (`ensure_dependencies`) — they're orthogonal.
        if remote.skill_dependencies:
            from app.services.skills.dependency_resolver import (
                SkillDependencyError,
                SkillDependencyResolver,
            )

            try:
                _, newly = await SkillDependencyResolver(
                    client=self.client, installer=self
                ).install_dependencies(remote)
                if newly:
                    logger.info(
                        "clawhub install resolved %d cross-skill deps for %s: %s",
                        len(newly),
                        nm,
                        newly,
                    )
            except SkillDependencyError as exc:
                return False, f"skill_dependency_failed:{exc}", None

        ver = (version or "latest").strip()
        if ver == "latest":
            ver = remote.version

        payload = await self.client.download_skill(nm, ver)
        if not payload:
            return False, "download_failed", None

        staging = self.skills_root / ".staging" / nm
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)

        yml_path = self._materialize_package(nm, payload, staging)
        if yml_path is None:
            shutil.rmtree(staging, ignore_errors=True)
            return False, "no_skill_manifest", None

        try:
            manifest_preview = load_skill_manifest(yml_path)
            final_dir = self.skills_root / manifest_preview.name.strip()
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(staging, ignore_errors=True)
            return False, f"manifest_invalid:{exc}"[:500], None

        if final_dir.exists():
            shutil.rmtree(final_dir, ignore_errors=True)
        shutil.move(str(staging), str(final_dir))
        staging_parent = self.skills_root / ".staging"
        if staging_parent.exists() and not any(staging_parent.iterdir()):
            staging_parent.rmdir()

        yml_final = self._find_skill_yaml(final_dir)
        if yml_final is None:
            shutil.rmtree(final_dir, ignore_errors=True)
            return False, "no_skill_manifest", None

        reg = get_plugin_skill_registry()
        try:
            manifest = load_skill_manifest(yml_final)
            await reg.ensure_dependencies(manifest.dependencies)
            reg.register(manifest)
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(final_dir, ignore_errors=True)
            logger.exception("skill register failed")
            return False, f"register_failed:{exc}"[:2000], None

        now = datetime.now(timezone.utc)
        # Phase 75 — carry remote category through to the local row so the
        # Marketplace UI can render the filter chip without a metadata round-trip.
        cat = (manifest.category or remote.category or "").strip().lower()
        row = InstalledSkill(
            name=manifest.name,
            version=manifest.version,
            source=SkillSource.CLAWHUB,
            source_url=f"clawhub://{nm}",
            installed_at=now,
            updated_at=now,
            status=SkillStatus.INSTALLED,
            pinned_version=None if version == "latest" else ver,
            publisher=remote.publisher,
            available_version=None,
            update_checked_at=now,
            category=cat,
        )
        installed.append(row)
        self._save_manifest(installed)

        logger.info(
            "clawhub skill installed name=%s version=%s",
            nm,
            manifest.version,
            extra={
                "nexa_event": "clawhub_install",
                "skill": nm,
                "version": manifest.version,
                "publisher": remote.publisher,
            },
        )
        return True, "ok", manifest.name

    def _materialize_package(self, name: str, payload: bytes, dest: Path) -> Path | None:
        """Extract ZIP or raw YAML; return path to skill.yaml."""
        _ = name
        if zipfile.is_zipfile(io.BytesIO(payload)):
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
                tf.write(payload)
                zpath = tf.name
            try:
                with zipfile.ZipFile(zpath, "r") as zf:
                    zf.extractall(dest)
            finally:
                Path(zpath).unlink(missing_ok=True)
        else:
            text = self._decode_maybe_yaml(payload)
            if text is None:
                return None
            yml = dest / "skill.yaml"
            yml.write_text(text, encoding="utf-8")

        return self._find_skill_yaml(dest)

    def _decode_maybe_yaml(self, payload: bytes) -> str | None:
        for enc in ("utf-8", "utf-8-sig"):
            try:
                s = payload.decode(enc)
                if s.lstrip().startswith("name:") or "\nname:" in s[:400]:
                    return s
            except UnicodeDecodeError:
                continue
        return None

    def _find_skill_yaml(self, root: Path) -> Path | None:
        for nm in ("skill.yaml", "skill.yml"):
            for p in root.rglob(nm):
                if p.is_file():
                    return p
        return None

    async def uninstall(self, name: str) -> tuple[bool, str]:
        nm = (name or "").strip()
        if not nm:
            return False, "invalid_name"

        installed = self._load_manifest()
        row = next((s for s in installed if s.name == nm), None)
        if row is None:
            return False, "not_found"

        reg = get_plugin_skill_registry()
        reg.unregister_skill(row.name)

        skill_dir = self.skills_root / row.name
        if skill_dir.exists():
            shutil.rmtree(skill_dir, ignore_errors=True)

        installed = [s for s in installed if s.name != row.name]
        self._save_manifest(installed)

        logger.info("clawhub skill removed name=%s", nm, extra={"nexa_event": "clawhub_uninstall", "skill": nm})
        return True, "ok"

    async def update(self, name: str, *, force: bool = False) -> tuple[bool, str]:
        nm = (name or "").strip()
        installed = self._load_manifest()
        skill = next((s for s in installed if s.name == nm), None)
        if not skill:
            return False, "not_found"
        if skill.source != SkillSource.CLAWHUB:
            return False, "not_clawhub"

        remote = await self.client.get_skill_info(nm)
        if not remote:
            return False, "remote_metadata_unavailable"
        if remote.version == skill.version:
            return True, "already_latest"

        ok_u, err_u = await self.uninstall(nm)
        if not ok_u:
            return False, err_u

        ok, msg, _key = await self.install(nm, remote.version, force=force)
        return ok, msg

    def list_installed(self) -> list[InstalledSkill]:
        return self._load_manifest()

    def mark_update_checked(
        self,
        name: str,
        *,
        available_version: str | None,
        checked_at: datetime | None = None,
    ) -> InstalledSkill | None:
        """Phase 75 — stamp ``available_version`` + ``update_checked_at`` for an installed row.

        Used by :class:`~app.services.skills.update_checker.SkillUpdateChecker`
        and the ``POST /-/check-updates-now`` endpoint. Setting
        ``available_version`` to a value that equals the installed
        ``version`` clears the indicator (we treat "matches installed" as
        "no update available"). This never auto-installs — apply via
        :func:`update`.

        Returns the updated :class:`InstalledSkill` row, or ``None`` if the
        skill isn't in the manifest.
        """
        nm = (name or "").strip()
        if not nm:
            return None
        installed = self._load_manifest()
        target: InstalledSkill | None = None
        for row in installed:
            if row.name == nm:
                row.update_checked_at = checked_at or datetime.now(timezone.utc)
                if available_version and available_version.strip() == row.version:
                    row.available_version = None
                else:
                    row.available_version = (
                        available_version.strip() if available_version else None
                    )
                # Status surface — flag stale rows as OUTDATED so callers
                # filtering by status don't have to recompute the comparison.
                if row.available_version:
                    row.status = SkillStatus.OUTDATED
                elif row.status == SkillStatus.OUTDATED:
                    row.status = SkillStatus.INSTALLED
                target = row
                break
        if target is None:
            return None
        self._save_manifest(installed)
        return target


__all__ = ["SkillInstaller"]
