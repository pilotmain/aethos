"""
Phase 11 — multi-provider LLM layer (registry + primary completion for :mod:`app.services.llm_service`).

Remote gateway tool missions continue to use :func:`app.services.providers.gateway.call_provider`.
"""

from app.services.llm.completion import get_llm, primary_complete_raw, providers_available

__all__ = ["get_llm", "primary_complete_raw", "providers_available"]
