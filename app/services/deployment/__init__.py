"""Generic CLI-based deployment detection and execution."""

from app.services.deployment.detector import DeploymentDetector
from app.services.deployment.executor import DeploymentExecutor

__all__ = ["DeploymentDetector", "DeploymentExecutor"]
