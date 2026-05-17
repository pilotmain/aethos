# SQLite operational stability

- WAL + 30s busy timeout on file-backed SQLite
- Bounded retries on schema init and migrations (`sqlite_retry`)
- Truth keys: `db_lock_waiting`, `db_lock_wait_ms`, `db_retry_count`, `db_owner_hint`, `db_last_error`
- Recovery: `aethos restart runtime`
