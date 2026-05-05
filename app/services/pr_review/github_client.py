"""
GitHub REST client for pull request review operations (httpx async).
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_GH_TIMEOUT = 60.0
_GH_API_VERSION = "2022-11-28"


class GitHubPRClient:
    """GitHub API client for PR review operations."""

    def __init__(self, token: str, repo_owner: str, repo_name: str) -> None:
        self._token = (token or "").strip()
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = "https://api.github.com"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _GH_API_VERSION,
        }

    def _repo_path(self) -> str:
        return f"/repos/{self.repo_owner}/{self.repo_name}"

    async def get_pr(self, pr_number: int) -> dict[str, Any] | None:
        url = f"{self.base_url}{self._repo_path()}/pulls/{pr_number}"
        async with httpx.AsyncClient(timeout=_GH_TIMEOUT) as client:
            r = await client.get(url, headers=self._headers())
            if r.status_code == 404:
                return None
            if not r.is_success:
                logger.warning("github get_pr failed status=%s body=%s", r.status_code, r.text[:500])
                try:
                    return r.json()
                except Exception:
                    return {"message": r.text, "status": r.status_code}
            return r.json()

    async def get_pr_files(self, pr_number: int) -> list[dict[str, Any]]:
        url = f"{self.base_url}{self._repo_path()}/pulls/{pr_number}/files"
        out: list[dict[str, Any]] = []
        page = 1
        per_page = 100
        async with httpx.AsyncClient(timeout=_GH_TIMEOUT) as client:
            while True:
                r = await client.get(
                    url,
                    headers=self._headers(),
                    params={"page": page, "per_page": per_page},
                )
                if not r.is_success:
                    logger.warning("github get_pr_files failed status=%s", r.status_code)
                    return out
                batch = r.json()
                if not isinstance(batch, list):
                    return out
                out.extend(batch)
                if len(batch) < per_page:
                    break
                page += 1
        return out

    async def get_file_content(self, file_path: str, ref: str) -> str | None:
        encoded = file_path.replace("/", "%2F")
        url = f"{self.base_url}{self._repo_path()}/contents/{encoded}"
        async with httpx.AsyncClient(timeout=_GH_TIMEOUT) as client:
            r = await client.get(url, headers=self._headers(), params={"ref": ref})
            if r.status_code != 200:
                return None
            data = r.json()
            if isinstance(data, dict) and data.get("encoding") == "base64" and data.get("content"):
                raw = base64.b64decode(data["content"].replace("\n", ""))
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError:
                    return raw.decode("utf-8", errors="replace")
            return None

    async def create_pull_request_review(
        self,
        pr_number: int,
        *,
        commit_id: str,
        body: str,
        event: str,
        comments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a PR review (COMMENT / APPROVE / REQUEST_CHANGES) with optional inline comments."""
        url = f"{self.base_url}{self._repo_path()}/pulls/{pr_number}/reviews"
        payload: dict[str, Any] = {
            "commit_id": commit_id,
            "body": body,
            "event": event,
        }
        if comments:
            payload["comments"] = comments
        async with httpx.AsyncClient(timeout=_GH_TIMEOUT) as client:
            r = await client.post(url, headers=self._headers(), json=payload)
            try:
                data = r.json()
            except Exception:
                data = {"message": r.text}
            if not r.is_success:
                logger.warning(
                    "github create_pull_request_review failed status=%s body=%s",
                    r.status_code,
                    r.text[:800],
                )
            return data if isinstance(data, dict) else {"raw": data}
