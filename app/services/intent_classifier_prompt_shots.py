# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Benchmark-aligned disambiguation + few-shots for intent classification.

Single source of truth for :data:`INTENT_CLASSIFIER_SYSTEM` in
``intent_classifier.py`` and for ``tests/benchmark/run_benchmark.py`` harness
prompts (``qwen2.5:7b`` agent-task suite).
"""

INTENT_CLASSIFIER_PROMPT_SHOTS = """
## Critical disambiguation (read before classifying)
- **greeting**: short social openers only (hi, hello, hey, good morning, howdy) with **no** real task yet. **Never** use general_chat for these.
- **general_chat**: trivia, small talk, factual Q&A, or chit-chat that is **not** a greeting-only line and **not** another intent.
- **brain_dump**: user lists **2+ concrete tasks/errands** or clear multi-item todo language — not a single imperative dev command. **Release-engineering checklists** (ship patch, changelog, tag, tests) are **brain_dump** unless they explicitly demand a **hosted** fix-push-verify **pipeline** (Railway/Render/production) — then **external_execution**.
- **create_sub_agent**: user wants a **named role/specialist agent** (marketing, QA, security, research, …) via registry — phrases like "create a … agent", "spawn a … agent", "I need a … specialist".
- **create_custom_agent**: legacy **user-defined agent profile** wording only when clearly about building a **custom profile/config**, not a role specialist (rare in benchmarks).
- **orchestrate_system**: status across **missions / Mission Control / dev runs / what succeeded or failed** — orchestration overview.
- **external_execution**: user wants an **end-to-end pipeline** on **hosted** infra (check logs, fix, push, redeploy, **verify production** / explicit hosted service). **Not** a simple local task list without hosted verification language.
- **external_execution_continue**: short confirmation continuing a prior **external execution / Railway / deploy** access thread.
- **external_investigation**: hosted provider health / outage / dashboard questions **without** demanding the full fix-push-verify pipeline.
- **stuck**: emotional **freeze / overwhelm about life or work in general** without a concrete task list or “not done yet” deferral.
- **followup_reply**: user reports **incomplete work** on something already in motion (“I didn’t finish”, “not done yet”, “still working on it”) — **not** stuck unless it is clearly emotional overwhelm, not task status. **Not** status_update: followup is about **incomplete** progress, not **done**.
- **status_update**: user reports **completed** or **done** work (“I finished…”, “completed the migration”, “shipped it yesterday”).
- **correction**: user **rejects** the assistant’s prior answer or demands it answer differently (“No, answer the question”, “you misunderstood”).
- **clarification**: vague product tweak with **no URL/stack/concrete goal** (“make my website better”, “improve my app”) — **not** help_request when the user is asking how to decide what to do next. **Not** analysis: **postmortem / root-cause / “analyze this [paste, trace, summary]”** on supplied material → **analysis**, not a vague tweak.
- **analysis**: asks for a **structured writeup or diagnosis of supplied material** — **postmortem**/RCA on an outage summary, “**analyze this** stack trace / log / document”. **Not** when the user is mainly **reporting a live project failure** (TypeError in code, eslint/pytest/CI failures) → that is **stuck_dev**.
- **help_request**: user wants **support, guidance, or help figuring out next steps** (“I need help”, “not sure what to ask”, “help me figure out what to do next”) — **not** greeting (no hi/hello opener required) and **not** clarification unless the message is **only** a vague product tweak with zero help-seeking.
- **config_query**: asks about **this deployment’s** configuration (which LLM, workspace path, whether keys are set — never the secret values).
- **capability_question**: asks what the assistant **can or cannot do** in a domain (“can you deploy”, “do you support agents”) — not “run npm test” style imperative.
- **dev_command**: imperative **run / show / print** (“run npm test”, “git status”) — **not** “tool X **fails** / **error** …” (those are **stuck_dev** failure reports, not commands).
- **stuck_dev**: **build, test, CI, lint, deploy, tooling** — user’s project is **broken or red** (TypeError, failing tests, eslint errors, CI red). Prefer **stuck_dev** over **analysis** when the line **reports a failure** rather than asking to postmortem/analyze a pasted artifact.

## Few-shot (your entire reply must be ONE JSON object only — no markdown, no text before or after)
User message: hello there
{"intent":"greeting","confidence":0.95,"reason":"short social opener"}

User message: hey team
{"intent":"greeting","confidence":0.92,"reason":"greeting to group"}

User message: buy milk, call dentist, finish the deck slides
{"intent":"brain_dump","confidence":0.9,"reason":"multiple concrete tasks listed"}

User message: create a marketing agent for me
{"intent":"create_sub_agent","confidence":0.9,"reason":"registry role specialist"}

User message: spawn a QA specialist agent
{"intent":"create_sub_agent","confidence":0.9,"reason":"spawn specialist"}

User message: give me mission control status on all runs
{"intent":"orchestrate_system","confidence":0.88,"reason":"orchestration status"}

User message: check railway logs, fix the code, push, redeploy, verify production
{"intent":"external_execution","confidence":0.9,"reason":"full hosted pipeline"}

User message: yes use the railway token I pasted
{"intent":"external_execution_continue","confidence":0.85,"reason":"continues deploy access thread"}

User message: is railway down for everyone right now
{"intent":"external_investigation","confidence":0.85,"reason":"hosted service health question"}

User message: I feel completely stuck and can't start
{"intent":"stuck","confidence":0.88,"reason":"overwhelm without task list"}

User message: pytest fails with a fixture error on CI
{"intent":"stuck_dev","confidence":0.9,"reason":"technical CI/test failure"}

User message: TypeError in my FastAPI route handler
{"intent":"stuck_dev","confidence":0.9,"reason":"runtime error in user code"}

User message: eslint fails with no-unused-vars
{"intent":"stuck_dev","confidence":0.9,"reason":"lint failure not an imperative command"}

User message: I didn't finish the task yet
{"intent":"followup_reply","confidence":0.9,"reason":"incomplete work update"}

User message: not done yet
{"intent":"followup_reply","confidence":0.88,"reason":"short deferral on progress"}

User message: No, answer the question I asked
{"intent":"correction","confidence":0.92,"reason":"rejects prior answer"}

User message: you misunderstood my request
{"intent":"correction","confidence":0.9,"reason":"meta correction"}

User message: make my website better
{"intent":"clarification","confidence":0.85,"reason":"vague product ask"}

User message: analyze this stack trace and root cause it
{"intent":"analysis","confidence":0.9,"reason":"structured technical diagnosis"}

User message: postmortem this outage summary
{"intent":"analysis","confidence":0.9,"reason":"incident postmortem is structured analysis"}

User message: what model are you using
{"intent":"config_query","confidence":0.9,"reason":"deployment LLM settings"}

User message: can you write code for me
{"intent":"capability_question","confidence":0.88,"reason":"asks if coding is supported"}

User message: run npm test in the repo root
{"intent":"dev_command","confidence":0.9,"reason":"imperative command"}

User message: ship the patch, update the changelog, and tag the release
{"intent":"brain_dump","confidence":0.9,"reason":"multi-item local release checklist not hosted pipeline"}

User message: I need help but I'm not sure what to ask
{"intent":"help_request","confidence":0.88,"reason":"seeks guidance not a greeting"}

User message: I finished the migration yesterday
{"intent":"status_update","confidence":0.92,"reason":"reports completed work"}

User message: help me figure out what to do next
{"intent":"help_request","confidence":0.88,"reason":"next-step guidance not vague product tweak"}
""".strip()
