"""Deduplication: URL-first, company+title+location as fallback."""
from typing import Any, Dict, List, Set, Tuple


def _url_key(job: Dict[str, Any]) -> str:
    return job.get("url", "").strip().rstrip("/").lower()


def _content_key(job: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        job.get("company", "").lower().strip(),
        job.get("title", "").lower().strip(),
        job.get("location", "").lower().strip(),
    )


def build_seen_sets(
    jobs: List[Dict[str, Any]],
) -> Tuple[Set[str], Set[Tuple[str, str, str]]]:
    seen_urls: Set[str] = set()
    seen_keys: Set[Tuple[str, str, str]] = set()
    for job in jobs:
        url = _url_key(job)
        if url:
            seen_urls.add(url)
        seen_keys.add(_content_key(job))
    return seen_urls, seen_keys


def deduplicate(
    new_jobs: List[Dict[str, Any]],
    existing_jobs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return jobs from new_jobs not already present in existing_jobs."""
    seen_urls, seen_keys = build_seen_sets(existing_jobs)

    unique: List[Dict[str, Any]] = []
    for job in new_jobs:
        url = _url_key(job)
        key = _content_key(job)

        if url and url in seen_urls:
            continue
        if key in seen_keys:
            continue

        # Mark seen so we don't emit intra-batch duplicates either
        if url:
            seen_urls.add(url)
        seen_keys.add(key)
        unique.append(job)

    return unique
