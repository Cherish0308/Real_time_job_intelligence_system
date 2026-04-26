"""Title + location filtering against configurable keyword lists."""
from typing import Any, Dict, List

from utils.config import config

_TITLE_KWS = [kw.lower() for kw in config.target_titles]
_LOC_KWS = [loc.lower() for loc in config.target_locations]


def _title_matches(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in _TITLE_KWS)


def _location_matches(location: str) -> bool:
    # Blank location → include (many remote roles omit location)
    if not location.strip():
        return True
    loc = " " + location.lower() + " "   # pad to help word-boundary matching
    return any(kw in loc for kw in _LOC_KWS)


def filter_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return only jobs matching target titles and US/remote locations."""
    return [
        job for job in jobs
        if _title_matches(job.get("title", ""))
        and _location_matches(job.get("location", ""))
    ]
