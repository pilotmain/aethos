"""Nexa / command-center strings for Telegram."""


WELCOME_NEXA = (
    "Welcome to **Nexa** — a personal AI command center for thinking, deciding, delegating, and executing. "
    "The **Reset Agent** handles overload, planning, and next steps. "
    "The **Dev Agent** runs the autonomous dev loop (with your approval) on your machine. "
    "Use /agents to see the full specialist roster."
)


def format_agents_list() -> str:
    return (
        "Nexa agents:\n\n"
        "🧠 @reset — turns chaos into next steps\n"
        "💻 @dev — works on code through your local worker\n"
        "🧪 @qa — reviews tests, failures, and regressions\n"
        "⚙️ @ops — checks worker health and execution state\n"
        "🧭 @strategy — helps with product, roadmap, and tradeoffs\n"
        "📣 @marketing — helps with copy, positioning, and launches\n"
        "🔎 @research — finds and summarizes information\n\n"
        "Use an agent directly:\n"
        "@dev add a README note\n"
        "@ops health"
    )


def format_command_center() -> str:
    return (
        "Nexa Command Center\n\n"
        "Agents:\n"
        "🧠 @reset — focus and overwhelm\n"
        "💻 @dev — code work through local worker\n"
        "🧪 @qa — tests and regressions\n"
        "⚙️ @ops — system health and queue\n"
        "🧭 @strategy — direction and roadmap\n"
        "📣 @marketing — messaging and launch\n"
        "🔎 @research — research and comparison\n\n"
        "Try:\n"
        "@dev fix the README typo\n"
        "@ops health\n"
        "@strategy what should we build next?"
    )
