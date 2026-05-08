"""
Phase 73b — Self-Improvement (Genesis Loop, safe-adapt v1).

This package houses the operator-driven proposal pipeline:

* :mod:`app.services.self_improvement.context`  — read-only allowlisted code
  context fetcher.
* :mod:`app.services.self_improvement.proposal` — generate / validate /
  persist unified-diff proposals (table ``self_improvement_proposals`` lives
  in the existing ``data/agent_audit.db``).
* :mod:`app.services.self_improvement.sandbox`  — isolated ``git worktree``
  runner that applies a candidate diff and runs ``compileall`` + a targeted
  ``pytest`` invocation (no GitHub API, no auto-push, no auto-restart).

The HTTP surface lives in :mod:`app.api.routes.self_improvement`. All
mutating endpoints are owner-gated and additionally guarded by
``NEXA_SELF_IMPROVEMENT_ENABLED`` (default ``False``).
"""

from __future__ import annotations

__all__: list[str] = []
