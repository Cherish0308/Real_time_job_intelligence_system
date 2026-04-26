"""Title + location filtering, and experience-level tagging."""
from typing import Any, Dict, List

from utils.config import config

_TITLE_KWS = [kw.lower() for kw in config.target_titles]
_LOC_KWS = [loc.lower() for loc in config.target_locations]
_SENIOR_KWS = [kw.lower() for kw in config.senior_keywords]
_ENTRY_KWS = [kw.lower() for kw in config.mid_entry_keywords]


def _title_matches(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in _TITLE_KWS)


def _location_matches(location: str) -> bool:
    if not location.strip():
        return True
    loc = " " + location.lower() + " "
    return any(kw in loc for kw in _LOC_KWS)


def tag_experience_level(title: str) -> str:
    """Return '5+' for senior roles, '0-5' for entry/mid, 'any' when unclear."""
    t = title.lower()
    if any(kw in t for kw in _SENIOR_KWS):
        return "5+"
    if any(kw in t for kw in _ENTRY_KWS):
        return "0-5"
    return "any"


def filter_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter by title/location and attach an experience_level tag to each job."""
    result = []
    for job in jobs:
        if _title_matches(job.get("title", "")) and _location_matches(job.get("location", "")):
            job = {**job, "experience_level": tag_experience_level(job.get("title", ""))}
            result.append(job)
    return result
