"""Atomic JSON persistence with age-based pruning."""
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from utils.config import config

logger = logging.getLogger(__name__)

_PATH = Path(config.storage_file)


def load_jobs() -> List[Dict[str, Any]]:
    if not _PATH.exists():
        return []
    try:
        with open(_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load %s: %s", _PATH, exc)
        return []


def _atomic_write(jobs: List[Dict[str, Any]]) -> None:
    """Write via temp file + rename so readers never see a partial file."""
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=_PATH.parent, prefix=".jobs_tmp_", suffix=".json"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(jobs, fh, indent=2, default=str)
        os.replace(tmp_path, _PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _prune(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.max_job_age_hours)
    kept = []
    for job in jobs:
        try:
            ts = datetime.fromisoformat(job["timestamp"].replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                kept.append(job)
        except (KeyError, ValueError):
            kept.append(job)   # unknown timestamp → keep
    return kept


def append_jobs(new_jobs: List[Dict[str, Any]]) -> None:
    """Merge new_jobs into storage, pruning stale entries."""
    existing = load_jobs()
    combined = _prune(existing + new_jobs)
    try:
        _atomic_write(combined)
    except OSError as exc:
        logger.error("Failed to persist jobs: %s", exc)
