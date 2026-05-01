"""
Third-party LLM SDK imports live **only** here (and in stub modules under this package).

Application code should import ``OpenAI`` / ``anthropic`` from this module—not from vendor packages—
so optional static checks can enforce the provider boundary.
"""

from __future__ import annotations

import anthropic
from openai import OpenAI

__all__ = ["OpenAI", "anthropic"]
