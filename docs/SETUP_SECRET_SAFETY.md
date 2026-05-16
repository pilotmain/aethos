# Setup secret safety

- Tokens are entered with hidden input where supported.
- Full tokens are not re-displayed after save (`mask_secret` / redacted summaries).
- `.env` backups are timestamped before overwrite (`scripts/setup_helpers/backup.py`).
- Setup logs use `redact_env_for_display` for summaries.
