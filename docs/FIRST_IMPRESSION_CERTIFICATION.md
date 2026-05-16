# First impression certification (Step 17)

Phase marker: `phase4_step17` (`installer_interaction_locked`).

Certifies:

- Global setup commands on prompts
- Progress persistence and resume
- Mission Control ready-state endpoints
- Bounded cold-hydration e2e
- Operator error copy

Run:

```bash
USE_REAL_LLM=false NEXA_PYTEST=1 pytest tests/test_setup_prompt_runtime.py tests/test_setup_progress_state.py tests/test_mission_control_ready_state.py tests/test_runtime_startup_ready_state.py tests/test_operator_error_copy.py tests/test_phase4_step17_runtime_evolution.py -q
```
