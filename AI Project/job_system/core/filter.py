"""Title + location filtering, recency check, and experience-level tagging."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from utils.config import config

_TITLE_KWS  = [kw.lower() for kw in config.target_titles]
_LOC_KWS    = [loc.lower() for loc in config.target_locations]
_SENIOR_KWS = [kw.lower() for kw in config.senior_keywords]
_ENTRY_KWS  = [kw.lower() for kw in config.mid_entry_keywords]


# ── Title / location ───────────────────────────────────────────────────────────

def _title_matches(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in _TITLE_KWS)


def _location_matches(location: str) -> bool:
    if not location.strip():
        return True          # blank = assume remote/flexible → include
    loc = " " + location.lower() + " "
    return any(kw in loc for kw in _LOC_KWS)


# ── Experience level ───────────────────────────────────────────────────────────

def tag_experience_level(title: str) -> str:
    """Return '5+' for senior roles, '0-5' for entry/mid, 'any' when unclear."""
    t = title.lower()
    if any(kw in t for kw in _SENIOR_KWS):
        return "5+"
    if any(kw in t for kw in _ENTRY_KWS):
        return "0-5"
    return "any"


# ── Recency ────────────────────────────────────────────────────────────────────

def is_recent(job: Dict[str, Any], max_days: int = None) -> bool:
    """Return True if the job was posted within `max_days` days.

    Checks `days_ago` (set by Workday fetcher) first, then falls back to
    parsing the ISO `timestamp` field (used by Greenhouse / Lever).
    """
    if max_days is None:
        max_days = config.recent_days

    # Workday sets this directly from "Posted X Days Ago"
    days_ago = job.get("days_ago")
    if days_ago is not None:
        return days_ago <= max_days

    # Greenhouse / Lever: parse timestamp
    ts_str = job.get("timestamp", "")
    if not ts_str:
        return True   # no timestamp info → don't exclude
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
        return ts >= cutoff
    except ValueError:
        return True   # unparseable → don't exclude


# ── Main pipeline steps ────────────────────────────────────────────────────────

def filter_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter by title + location and attach experience_level tag."""
    result = []
    for job in jobs:
        if _title_matches(job.get("title", "")) and _location_matches(job.get("location", "")):
            result.append({**job, "experience_level": tag_experience_level(job.get("title", ""))})
    return result


def filter_recent(jobs: List[Dict[str, Any]], max_days: int = None) -> List[Dict[str, Any]]:
    """Keep only jobs posted within max_days. Older jobs are dropped."""
    return [j for j in jobs if is_recent(j, max_days)]
