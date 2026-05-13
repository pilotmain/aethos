# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

import re

import pytest

from app.core.web_api_token import generate_web_api_token


def test_generate_web_api_token_length_and_charset() -> None:
    t = generate_web_api_token(32)
    assert len(t) == 32
    assert re.fullmatch(r"[A-Za-z0-9_-]+", t)


def test_generate_web_api_token_min_length() -> None:
    with pytest.raises(ValueError):
        generate_web_api_token(8)
