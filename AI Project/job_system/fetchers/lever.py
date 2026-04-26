"""Lever jobs API fetcher.

Docs: https://hire.lever.co/developer/postings
Endpoint: GET https://api.lever.co/v0/postings/{company}?mode=json
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from .base import BaseFetcher
from utils.config import config

logger = logging.getLogger(__name__)

_BASE = "https://api.lever.co/v0/postings/{company}?mode=json"
_TIMEOUT = aiohttp.ClientTimeout(total=config.request_timeout)


def _extract_location(job: Dict) -> str:
    categories = job.get("categories") or {}

    # Primary: categories.location
    loc = categories.get("location", "")
    if loc:
        return loc.strip()

    # Fallback: categories.allLocations list
    all_locs: Optional[List[str]] = categories.get("allLocations")
    if isinstance(all_locs, list) and all_locs:
        return all_locs[0].strip()

    # Last resort: top-level workplaceType
    wtype = job.get("workplaceType", "")
    if wtype.lower() == "remote":
        return "Remote"

    return ""


def _ms_to_iso(ms: Optional[int]) -> str:
    if ms:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


class LeverFetcher(BaseFetcher):
    source_name = "lever"

    async def fetch_company(
        self, company: str, session: aiohttp.ClientSession
    ) -> List[Dict[str, Any]]:
        url = _BASE.format(company=company)
        try:
            async with session.get(url, timeout=_TIMEOUT) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    jobs = data if isinstance(data, list) else []
                    return self._normalize(jobs, company)
                if resp.status == 404:
                    logger.debug("Lever: %s not found (404)", company)
                else:
                    logger.warning("Lever %s: HTTP %s", company, resp.status)
        except asyncio.TimeoutError:
            logger.warning("Lever %s: request timed out", company)
        except aiohttp.ClientError as exc:
            logger.error("Lever %s: %s", company, exc)
        except Exception as exc:
            logger.error("Lever %s: unexpected error: %s", company, exc)
        return []

    def _normalize(self, jobs: List[Dict], company: str) -> List[Dict[str, Any]]:
        out = []
        for job in jobs:
            out.append({
                "id": f"lever_{job.get('id', '')}",
                "company": company,
                "title": job.get("text", ""),
                "location": _extract_location(job),
                "url": job.get("hostedUrl", ""),
                "source": self.source_name,
                "timestamp": _ms_to_iso(job.get("createdAt")),
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
