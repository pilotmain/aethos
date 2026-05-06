"""
Universal cloud provider registry — declarative CLI shapes + NL detection.

Providers are **best-effort**: deploy/log commands vary by project; tokens come from the user environment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ProviderCapability(str, Enum):
    DEPLOY = "deploy"
    LOGS = "logs"
    STATUS = "status"
    DESTROY = "destroy"
    LIST = "list"
    ENV = "env"


@dataclass
class CloudProvider:
    """Definition of a cloud provider CLI."""

    name: str
    display_name: str
    cli_package: Optional[str] = None
    install_command: Optional[str] = None
    token_env_var: Optional[str] = None
    project_id_env_var: Optional[str] = None
    capabilities: list[ProviderCapability] = field(default_factory=list)
    detect_patterns: list[str] = field(default_factory=list)
    deploy_command: list[str] = field(default_factory=list)
    logs_command: list[str] = field(default_factory=list)
    status_command: list[str] = field(default_factory=list)
    destroy_command: list[str] = field(default_factory=list)
    list_command: list[str] = field(default_factory=list)


class CloudProviderRegistry:
    """Registry of supported providers (extensible via :meth:`register`)."""

    def __init__(self) -> None:
        self._providers: dict[str, CloudProvider] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(
            CloudProvider(
                name="railway",
                display_name="Railway",
                cli_package="@railway/cli",
                install_command="npm install -g @railway/cli",
                token_env_var="RAILWAY_TOKEN",
                project_id_env_var="RAILWAY_PROJECT_ID",
                capabilities=[
                    ProviderCapability.DEPLOY,
                    ProviderCapability.LOGS,
                    ProviderCapability.STATUS,
                ],
                detect_patterns=["railway.app", "railway", "rail way"],
                deploy_command=["railway", "up", "--detach"],
                logs_command=["railway", "logs"],
                status_command=["railway", "status"],
            )
        )
        self.register(
            CloudProvider(
                name="vercel",
                display_name="Vercel",
                cli_package="vercel",
                install_command="npm install -g vercel",
                token_env_var="VERCEL_TOKEN",
                capabilities=[
                    ProviderCapability.DEPLOY,
                    ProviderCapability.LOGS,
                    ProviderCapability.LIST,
                    ProviderCapability.ENV,
                ],
                detect_patterns=["vercel.com", "vercel"],
                deploy_command=["vercel", "deploy", "--prod", "--yes"],
                logs_command=["vercel", "logs"],
                list_command=["vercel", "projects", "list", "--output", "json"],
            )
        )
        self.register(
            CloudProvider(
                name="aws",
                display_name="AWS",
                cli_package="awscli",
                install_command="pip install awscli",
                token_env_var="AWS_ACCESS_KEY_ID",
                capabilities=[
                    ProviderCapability.DEPLOY,
                    ProviderCapability.LOGS,
                    ProviderCapability.STATUS,
                    ProviderCapability.DESTROY,
                ],
                detect_patterns=[
                    "amazon web services",
                    "cloudformation",
                    "aws lambda",
                    "amazon",
                    "aws ",
                    "aws/",
                    " ec2",
                    "lambda",
                    "s3 bucket",
                    "aws",
                ],
                deploy_command=["aws", "cloudformation", "deploy"],
                logs_command=["aws", "logs", "tail"],
                status_command=["aws", "cloudformation", "describe-stacks"],
            )
        )
        self.register(
            CloudProvider(
                name="gcp",
                display_name="Google Cloud",
                cli_package="google-cloud-sdk",
                install_command="https://cloud.google.com/sdk/docs/install",
                token_env_var="GOOGLE_APPLICATION_CREDENTIALS",
                project_id_env_var="GCP_PROJECT_ID",
                capabilities=[
                    ProviderCapability.DEPLOY,
                    ProviderCapability.LOGS,
                    ProviderCapability.STATUS,
                ],
                detect_patterns=[
                    "google cloud platform",
                    "cloud run",
                    "google cloud",
                    "gcloud",
                    "gcp",
                ],
                deploy_command=["gcloud", "run", "deploy"],
                logs_command=["gcloud", "logging", "read"],
                status_command=["gcloud", "run", "services", "list"],
            )
        )
        self.register(
            CloudProvider(
                name="heroku",
                display_name="Heroku",
                cli_package="heroku-cli",
                install_command="https://devcenter.heroku.com/articles/heroku-cli",
                token_env_var="HEROKU_API_KEY",
                capabilities=[
                    ProviderCapability.DEPLOY,
                    ProviderCapability.LOGS,
                    ProviderCapability.STATUS,
                    ProviderCapability.DESTROY,
                ],
                detect_patterns=["heroku.com", "heroku"],
                deploy_command=["git", "push", "heroku", "main"],
                logs_command=["heroku", "logs", "--tail"],
                status_command=["heroku", "ps"],
            )
        )
        self.register(
            CloudProvider(
                name="fly",
                display_name="Fly.io",
                cli_package="flyctl",
                install_command="curl -L https://fly.io/install.sh | sh",
                token_env_var="FLY_API_TOKEN",
                capabilities=[
                    ProviderCapability.DEPLOY,
                    ProviderCapability.LOGS,
                    ProviderCapability.STATUS,
                ],
                detect_patterns=["fly.io", "fly io", "flyctl", " fly "],
                deploy_command=["fly", "deploy"],
                logs_command=["fly", "logs"],
                status_command=["fly", "status"],
            )
        )
        self.register(
            CloudProvider(
                name="netlify",
                display_name="Netlify",
                cli_package="netlify-cli",
                install_command="npm install -g netlify-cli",
                token_env_var="NETLIFY_AUTH_TOKEN",
                capabilities=[
                    ProviderCapability.DEPLOY,
                    ProviderCapability.LOGS,
                    ProviderCapability.LIST,
                ],
                detect_patterns=["netlify.app", "netlify"],
                deploy_command=["netlify", "deploy", "--prod"],
                logs_command=["netlify", "logs"],
                list_command=["netlify", "sites", "list"],
            )
        )
        self.register(
            CloudProvider(
                name="cloudflare",
                display_name="Cloudflare Workers",
                cli_package="wrangler",
                install_command="npm install -g wrangler",
                token_env_var="CLOUDFLARE_API_TOKEN",
                capabilities=[
                    ProviderCapability.DEPLOY,
                    ProviderCapability.LOGS,
                    ProviderCapability.STATUS,
                ],
                detect_patterns=["cloudflare workers", "wrangler", "cloudflare"],
                deploy_command=["wrangler", "deploy"],
                logs_command=["wrangler", "tail"],
                status_command=["wrangler", "whoami"],
            )
        )
        self.register(
            CloudProvider(
                name="azure",
                display_name="Azure",
                cli_package="azure-cli",
                install_command="https://learn.microsoft.com/cli/azure/install-azure-cli",
                token_env_var="AZURE_CLIENT_SECRET",
                capabilities=[ProviderCapability.DEPLOY, ProviderCapability.LOGS, ProviderCapability.STATUS],
                detect_patterns=["azure ", "microsoft azure", " az ", "azure/cli"],
                deploy_command=["az", "deployment", "group", "create"],
                logs_command=["az", "monitor", "activity-log", "list"],
                status_command=["az", "account", "show"],
            )
        )

    def register(self, provider: CloudProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> CloudProvider | None:
        return self._providers.get((name or "").strip().lower())

    def detect_from_text(self, text: str) -> CloudProvider | None:
        """Prefer the **longest** matching pattern across providers (reduces ambiguity)."""
        t = (text or "").lower()
        if not t.strip():
            return None

        scored: list[tuple[int, CloudProvider]] = []
        for p in self._providers.values():
            pats = sorted({x.lower() for x in (p.detect_patterns or [])}, key=len, reverse=True)
            for pat in pats:
                if len(pat) >= 5:
                    hit = pat in t
                else:
                    hit = bool(re.search(rf"\b{re.escape(pat)}\b", t))
                if hit:
                    scored.append((len(pat), p))
                    break
        if not scored:
            return None
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]

    def list_all(self) -> list[CloudProvider]:
        return sorted(self._providers.values(), key=lambda x: x.display_name.lower())


_registry: CloudProviderRegistry | None = None


def get_provider_registry() -> CloudProviderRegistry:
    global _registry
    if _registry is None:
        _registry = CloudProviderRegistry()
    return _registry


__all__ = [
    "CloudProvider",
    "CloudProviderRegistry",
    "ProviderCapability",
    "get_provider_registry",
]
