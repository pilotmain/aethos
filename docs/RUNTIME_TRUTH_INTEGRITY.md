# Runtime truth integrity

`GET /api/v1/mission-control/runtime/integrity` validates truth cohesion: duplicate keys, oversized branches, stale sections, and `truth_integrity_score`.

Implemented in `app/services/mission_control/runtime_truth_integrity.py`.
