"""Orchestrates one full fetch → filter → dedupe → store → alert cycle."""
import asyncio
import logging
from typing import Any, Dict, List

from fetchers.greenhouse import GreenhouseFetcher
from fetchers.lever import LeverFetcher
from core.filter import filter_jobs
from core.deduplicator import deduplicate
from core.storage import load_jobs, append_jobs
from alerts.slack import send_alert
from utils.config import config

logger = logging.getLogger(__name__)


async def run_fetch_cycle() -> List[Dict[str, Any]]:
    """Execute one polling cycle. Returns list of newly discovered jobs."""
    greenhouse = GreenhouseFetcher()
    lever = LeverFetcher()

    logger.info("Fetching from Greenhouse (%d) + Lever (%d) companies …",
                len(config.greenhouse_companies), len(config.lever_companies))

    gh_jobs, lv_jobs = await asyncio.gather(
        greenhouse.fetch_all(config.greenhouse_companies),
        lever.fetch_all(config.lever_companies),
    )

    raw_total = len(gh_jobs) + len(lv_jobs)
    logger.info("Raw fetched: %d (GH=%d, LV=%d)", raw_total, len(gh_jobs), len(lv_jobs))

    filtered = filter_jobs(gh_jobs + lv_jobs)
    logger.info("After filter: %d jobs", len(filtered))

    existing = load_jobs()
    new_jobs = deduplicate(filtered, existing)
    logger.info("New (unseen): %d jobs", len(new_jobs))

    if new_jobs:
        append_jobs(new_jobs)
        for job in new_jobs:
            send_alert(job)

    return new_jobs
