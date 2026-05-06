"""
Optional integration with gitleaks, trufflehog, and pip-audit (when installed).
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AdvancedSecurityScanner:
    """Run external secret / dependency scanners if present on PATH."""

    def __init__(self, root_path: str | Path):
        self.root_path = Path(root_path).resolve()
        self.has_gitleaks = shutil.which("gitleaks") is not None
        self.has_trufflehog = shutil.which("trufflehog") is not None
        self.has_pip_audit = shutil.which("pip-audit") is not None
        self.has_git = shutil.which("git") is not None

    def scan_with_gitleaks(self) -> dict[str, Any]:
        if not self.has_gitleaks:
            return {"available": False, "findings": [], "error": None}
        rep = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w+",
                suffix=".json",
                delete=False,
            ) as tf:
                rep = Path(tf.name)
            cmd: list[str] = [
                "gitleaks",
                "detect",
                "--source",
                str(self.root_path),
                "--report-format",
                "json",
                "--report-path",
                str(rep),
            ]
            if (self.root_path / ".git").is_dir() is False:
                cmd.append("--no-git")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.root_path),
            )
            if not rep.is_file() or rep.stat().st_size == 0:
                if result.returncode not in (0, 1, 2):
                    return {
                        "available": True,
                        "findings": [],
                        "error": (result.stderr or result.stdout or "gitleaks failed")[:2000],
                    }
                return {"available": True, "findings": [], "error": None}
            raw = rep.read_text(encoding="utf-8", errors="ignore")
            data = json.loads(raw) if raw.strip() else []
            findings: list[Any]
            if isinstance(data, list):
                findings = data
            elif isinstance(data, dict):
                findings = (
                    data.get("findings")
                    or data.get("leaks")
                    or data.get("Leaks")
                    or data.get("Results")
                    or []
                )
            else:
                findings = []
            if not isinstance(findings, list):
                findings = []
            return {"available": True, "findings": findings, "error": None}
        except json.JSONDecodeError as exc:
            logger.warning("gitleaks JSON parse failed: %s", exc)
            return {"available": True, "findings": [], "error": str(exc)[:500]}
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("gitleaks scan failed: %s", exc)
            return {"available": True, "findings": [], "error": str(exc)[:500]}
        finally:
            if rep is not None:
                try:
                    rep.unlink()
                except OSError:
                    pass

    def scan_with_trufflehog(self) -> dict[str, Any]:
        if not self.has_trufflehog:
            return {"available": False, "findings": [], "error": None}
        try:
            result = subprocess.run(
                [
                    "trufflehog",
                    "filesystem",
                    str(self.root_path),
                    "--json",
                    "--no-update",
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
            findings: list[dict[str, Any]] = []
            for line in (result.stdout or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    findings.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return {
                "available": True,
                "findings": findings,
                "error": None
                if result.returncode in (0, 1)
                else (result.stderr or "")[:1000],
            }
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("trufflehog scan failed: %s", exc)
            return {"available": True, "findings": [], "error": str(exc)[:500]}

    def scan_dependencies(self) -> dict[str, Any]:
        results: dict[str, Any] = {
            "vulnerabilities": [],
            "available": False,
            "error": None,
        }
        req = self.root_path / "requirements.txt"
        if not req.is_file():
            return results
        try:
            import importlib.util

            has_module = importlib.util.find_spec("pip_audit") is not None
        except Exception:
            has_module = False
        if not self.has_pip_audit and not has_module:
            return results
        cmd: list[str]
        if self.has_pip_audit:
            cmd = [
                "pip-audit",
                "--requirement",
                str(req),
                "--format",
                "json",
            ]
        else:
            cmd = [sys.executable, "-m", "pip_audit", "-r", str(req), "-f", "json"]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.root_path),
            )
            if not result.stdout or not result.stdout.strip():
                results["available"] = True
                return results
            data = json.loads(result.stdout)
            vulns: list[Any]
            if isinstance(data, list):
                vulns = data
            elif isinstance(data, dict):
                vulns = data.get("dependencies") or data.get("vulnerabilities") or data.get("results") or []
            else:
                vulns = []
            if not isinstance(vulns, list):
                vulns = []
            results["vulnerabilities"] = vulns
            results["available"] = True
        except (json.JSONDecodeError, OSError, subprocess.SubprocessError) as exc:
            logger.warning("pip-audit failed: %s", exc)
            results["error"] = str(exc)[:500]
        return results
