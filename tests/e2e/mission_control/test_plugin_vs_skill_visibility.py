# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_plugin_marketplace_clarity import (
    test_docs_describe_plugin_vs_skill_split,
    test_truth_separates_plugins_and_marketplace,
)


def test_e2e_plugin_vs_skill_visibility() -> None:
    test_truth_separates_plugins_and_marketplace()
    test_docs_describe_plugin_vs_skill_split()
