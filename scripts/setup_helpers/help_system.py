"""Built-in help topics for the setup wizard (type ``help`` or ``?`` at prompts)."""

from __future__ import annotations

from .colors import Colors


class HelpSystem:
    """Topic-based help text."""

    TOPICS: dict[str, dict[str, str]] = {
        "setup": {
            "title": "Setup overview",
            "content": """
This wizard walks through:
  1. System checks (Python, disk, ports)
  2. Python dependencies (pip / editable install)
  3. Environment file (.env from .env.example when present)
  4. Optional LLM API keys
  5. Database initialization (SQLite default)
  6. Optional local API start for smoke checks
  7. Post-setup HTTP validation

At any prompt, type ``help``, ``?``, or ``help <topic>`` (e.g. ``help llm``).
""",
        },
        "api": {
            "title": "API configuration",
            "content": """
The HTTP API defaults to port **8010** in this project (see ``API_BASE_URL``).

- Pick a free port if 8010 is taken.
- ``DATABASE_URL`` defaults to SQLite under ``~/.aethos/data/`` when unset.
- ``NEXA_WEB_API_TOKEN`` secures Mission Control headers when set.
""",
        },
        "telegram": {
            "title": "Telegram bot",
            "content": """
1. Open Telegram and talk to **@BotFather**
2. Run ``/newbot`` and follow prompts
3. Copy the bot token into ``TELEGRAM_BOT_TOKEN`` in ``.env``
4. Run the bot: ``python -m app.bot.telegram_bot`` (or embed with the API if configured)
""",
        },
        "llm": {
            "title": "LLM providers",
            "content": """
AethOS can use **Anthropic**, **OpenAI**, **DeepSeek**, **OpenRouter**, etc.

Set at least one key you plan to use, e.g.:
  ``ANTHROPIC_API_KEY``, ``OPENAI_API_KEY``, ``DEEPSEEK_API_KEY``

You can add more later by editing ``.env``.
""",
        },
        "auth": {
            "title": "Mission Control authentication",
            "content": """
The API expects:

• ``X-User-Id`` — canonical web user id (e.g. ``web_label``, ``tg_123456789``).

• ``Authorization: Bearer <NEXA_WEB_API_TOKEN>`` when ``NEXA_WEB_API_TOKEN`` is set in ``.env``.

The wizard saves ``TEST_X_USER_ID`` for your chosen id and generates ``NEXA_WEB_API_TOKEN``.
Use the same values in the web UI connection settings.
""",
        },
        "troubleshoot": {
            "title": "Common issues",
            "content": """
- **Port in use**: choose another port or stop the process using it.
- **401 on API**: set ``NEXA_WEB_API_TOKEN`` and send ``Authorization: Bearer …``.
- **Invalid X-User-Id**: use a valid id like ``web_myuser`` or ``tg_123456789``.
- **DB errors**: ensure ``DATABASE_URL`` points to a writable path; run ``aethos init-db``.
""",
        },
    }

    @classmethod
    def show(cls, topic: str | None = None) -> None:
        print(f"\n{Colors.BOLD}{Colors.CYAN}Help{Colors.RESET}\n")
        key = (topic or "").strip().lower()
        if key in cls.TOPICS:
            data = cls.TOPICS[key]
            print(f"{Colors.BOLD}{Colors.GREEN}{data['title']}{Colors.RESET}")
            print(data["content"])
        else:
            print(f"{Colors.BOLD}Topics:{Colors.RESET}")
            for t, data in cls.TOPICS.items():
                print(f"  {Colors.CYAN}{t}{Colors.RESET} — {data['title']}")
            print(f"\n{Colors.DIM}Example: help llm{Colors.RESET}")
        print()
