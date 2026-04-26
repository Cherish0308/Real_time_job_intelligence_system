"""Orchestrates one full fetch → filter → recency → dedupe → store → alert cycle."""
import asyncio
import logging
from typing import Any, Dict, List

from fetchers.greenhouse import GreenhouseFetcher
from fetchers.lever import LeverFetcher
from fetchers.workday import WorkdayFetcher
from core.filter import filter_jobs, filter_recent
from core.deduplicator import deduplicate
from core.storage import load_jobs, append_jobs
from alerts.slack import send_alert
from utils.config import config

logger = logging.getLogger(__name__)


async def run_fetch_cycle() -> List[Dict[str, Any]]:
    """Execute one polling cycle. Returns list of newly discovered jobs."""
    greenhouse = GreenhouseFetcher()
    lever = LeverFetcher()
    workday = WorkdayFetcher()

    logger.info(
        "Fetching: Greenhouse(%d) + Lever(%d) + Workday(%d) companies …",
        len(config.greenhouse_companies),
        len(config.lever_companies),
        len(config.workday_companies),
    )

    gh_jobs, lv_jobs, wd_jobs = await asyncio.gather(
        greenhouse.fetch_all(config.greenhouse_companies),
        lever.fetch_all(config.lever_companies),
        workday.fetch_all(config.workday_companies),
    )

    raw_total = len(gh_jobs) + len(lv_jobs) + len(wd_jobs)
    logger.info(
        "Raw fetched: %d  (GH=%d, LV=%d, WD=%d)",
        raw_total, len(gh_jobs), len(lv_jobs), len(wd_jobs),
    )

    # Step 1 — title + location filter
    filtered = filter_jobs(gh_jobs + lv_jobs + wd_jobs)
    logger.info("After title/location filter: %d jobs", len(filtered))

    # Step 2 — recency filter (only jobs posted within config.recent_days)
    recent = filter_recent(filtered)
    logger.info(
        "After recency filter (≤%d days): %d jobs", config.recent_days, len(recent)
    )

    # Step 3 — deduplicate against already-stored jobs
    existing = load_jobs()
    new_jobs = deduplicate(recent, existing)
    logger.info("New (unseen): %d jobs", len(new_jobs))

    if new_jobs:
        append_jobs(new_jobs)
        for job in new_jobs:
            send_alert(job)

    return new_jobs
