# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from unittest.mock import patch

from aethos_cli.setup_actionable_recovery import handle_db_lock_recovery, prompt_db_lock_recovery


def test_db_lock_recovery_later_noninteractive() -> None:
    with patch.dict(os.environ, {"NEXA_NONINTERACTIVE": "1"}, clear=False):
        action = prompt_db_lock_recovery()
    assert action == "later"


def test_handle_db_lock_use_existing_returns_zero(tmp_path) -> None:
    rc = handle_db_lock_recovery("use_existing", repo_root=tmp_path)
    assert rc == 0
