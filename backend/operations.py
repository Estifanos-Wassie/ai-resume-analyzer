"""Structured operational events with an explicit metadata allowlist."""

import json
import logging

logger = logging.getLogger("resume_analyzer.operations")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def log_analysis(request_id: str, duration_ms: float, outcome: str, status_code: int):
    logger.info(json.dumps({
        "event": "analysis_completed",
        "request_id": request_id,
        "duration_ms": round(duration_ms, 2),
        "outcome": outcome,
        "status_code": status_code,
    }))
