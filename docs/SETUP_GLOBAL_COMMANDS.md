# Setup global commands (Phase 4 Step 17)

Every interactive setup prompt wired through `aethos_cli/setup_prompt_runtime.py` supports:

`help` · `why` · `skip` · `back` · `resume` · `status` · `recommended` · `current` · `repair` · `quit`

- **help** — context-aware help for the current section
- **why** — why this step matters
- **skip** — only when the prompt allows skip
- **back** — limited in linear wizard; use `aethos setup resume`
- **resume** — shows saved progress from `~/.aethos/setup/setup_progress.json`
- **status** — completed / pending / failed sections
- **recommended** — applies the suggested value when available
- **current** — shows saved value (secrets redacted)
- **repair** — points to `aethos setup repair` / `aethos doctor`
- **quit** — saves progress and exits safely

Wired in: `setup_wizard.py`, onboarding, channels, web search, orchestrator onboarding.
