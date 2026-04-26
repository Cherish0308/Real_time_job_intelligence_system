"""Greenhouse jobs board API fetcher.

Docs: https://developers.greenhouse.io/job-board.html
Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{company}/jobs
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import aiohttp

from .base import BaseFetcher
from utils.config import config

logger = logging.getLogger(__name__)

_BASE = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
_TIMEOUT = aiohttp.ClientTimeout(total=config.request_timeout)


class GreenhouseFetcher(BaseFetcher):
    source_name = "greenhouse"

    async def fetch_company(
        self, company: str, session: aiohttp.ClientSession
    ) -> List[Dict[str, Any]]:
        url = _BASE.format(company=company)
        try:
            async with session.get(url, timeout=_TIMEOUT) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return self._normalize(data.get("jobs", []), company)
                if resp.status == 404:
                    logger.debug("Greenhouse: %s not found (404)", company)
                else:
                    logger.warning("Greenhouse %s: HTTP %s", company, resp.status)
        except asyncio.TimeoutError:
            logger.warning("Greenhouse %s: request timed out", company)
        except aiohttp.ClientError as exc:
            logger.error("Greenhouse %s: %s", company, exc)
        except Exception as exc:
            logger.error("Greenhouse %s: unexpected error: %s", company, exc)
        return []

    def _normalize(self, jobs: List[Dict], company: str) -> List[Dict[str, Any]]:
        out = []
        now = datetime.now(timezone.utc).isoformat()
        for job in jobs:
            loc = job.get("location", {})
            location = loc.get("name", "") if isinstance(loc, dict) else str(loc)

            out.append({
                "id": f"greenhouse_{job.get('id', '')}",
                "company": company,
                "title": job.get("title", ""),
                "location": location.strip(),
                "url": job.get("absolute_url", ""),
                "source": self.source_name,
                "timestamp": job.get("updated_at") or now,
            })
        return out

    async def fetch_all(self, companies: List[str]) -> List[Dict[str, Any]]:
        sem = asyncio.Semaphore(config.max_concurrent_requests)

        async def _guarded(company: str, session: aiohttp.ClientSession):
            async with sem:
                return await self.fetch_company(company, session)

        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                *[_guarded(c, session) for c in companies],
                return_exceptions=False,
            )
        return [job for batch in results for job in batch]
