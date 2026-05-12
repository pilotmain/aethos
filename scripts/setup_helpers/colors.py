# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""ANSI styling for terminal setup wizard output."""


class Colors:
    """ANSI color codes for readable, consistent CLI feedback."""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"

    @classmethod
    def success(cls, text: str) -> str:
        return f"{cls.GREEN}✓{cls.RESET} {text}"

    @classmethod
    def error(cls, text: str) -> str:
        return f"{cls.RED}✗{cls.RESET} {text}"

    @classmethod
    def warning(cls, text: str) -> str:
        return f"{cls.YELLOW}⚠{cls.RESET} {text}"

    @classmethod
    def info(cls, text: str) -> str:
        return f"{cls.BLUE}ℹ{cls.RESET} {text}"

    @classmethod
    def question(cls, text: str) -> str:
        return f"{cls.CYAN}?{cls.RESET} {text}"

    @classmethod
    def header(cls, text: str, width: int = 60) -> str:
        bar = "=" * width
        return (
            f"\n{cls.BOLD}{cls.HEADER}{bar}{cls.RESET}\n"
            f"{cls.BOLD}{cls.HEADER}{text.center(width)}{cls.RESET}\n"
            f"{cls.BOLD}{cls.HEADER}{bar}{cls.RESET}\n"
        )

    @classmethod
    def step(cls, num: int, total: int, text: str) -> str:
        return f"{cls.CYAN}[{num}/{total}]{cls.RESET} {text}"
