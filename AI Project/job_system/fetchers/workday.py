"""Workday job board API fetcher.

Workday exposes an internal JSON search endpoint used by every company's
career site. We POST a search query and receive structured job data —
no Selenium, no HTML parsing required.

Endpoint pattern:
  POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from .base import BaseFetcher
from utils.config import config

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=config.request_timeout)
_ENDPOINT = "https://{tenant}.wd{n}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; JobFetcher/1.0)",
}
_SEARCH_TERMS = [
    "data scientist",
    "machine learning",
    "data engineer",
    "ai engineer",
]


def _parse_posted_on(posted_on: str) -> Optional[int]:
    """Parse Workday's 'postedOn' text into days ago (int).

    Examples:
        'Posted Today'         → 0
        'Posted Yesterday'     → 1
        'Posted 3 Days Ago'    → 3
        'Posted 30+ Days Ago'  → 30
    """
    text = posted_on.lower()
    if "today" in text:
        return 0
    if "yesterday" in text:
        return 1
    match = re.search(r"(\d+)\+?\s+day", text)
    if match:
        return int(match.group(1))
    return None


def _days_ago_to_iso(days: Optional[int]) -> str:
    from datetime import timedelta
    if days is None:
        return datetime.now(timezone.utc).isoformat()
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.isoformat()


class WorkdayFetcher(BaseFetcher):
    source_name = "workday"

    async def _search_company(
        self,
        company_cfg: Dict[str, str],
        search_term: str,
        session: aiohttp.ClientSession,
        sem: asyncio.Semaphore,
    ) -> List[Dict[str, Any]]:
        tenant = company_cfg["tenant"]
        n = company_cfg["wd"]
        board = company_cfg["board"]
        url = _ENDPOINT.format(tenant=tenant, n=n, board=board)
        payload = {
            "appliedFacets": {},
            "limit": 50,
            "offset": 0,
            "searchText": search_term,
        }
        async with sem:
            try:
                async with session.post(
                    url, json=payload, headers=_HEADERS, timeout=_TIMEOUT
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        return self._normalize(
                            data.get("jobPostings", []),
                            company_cfg,
                            url,
                        )
                    if resp.status == 404:
                        logger.debug("Workday %s: 404 (board not found)", tenant)
                    else:
                        logger.warning("Workday %s: HTTP %s", tenant, resp.status)
            except asyncio.TimeoutError:
                logger.warning("Workday %s: timeout", tenant)
            except aiohttp.ClientError as exc:
                logger.error("Workday %s: %s", tenant, exc)
            except Exception as exc:
                logger.error("Workday %s: unexpected: %s", tenant, exc)
        return []

    def _normalize(
        self,
        postings: List[Dict],
        company_cfg: Dict[str, str],
        base_url: str,
    ) -> List[Dict[str, Any]]:
        tenant = company_cfg["tenant"]
        n = company_cfg["wd"]
        board = company_cfg["board"]
        base = f"https://{tenant}.wd{n}.myworkdayjobs.com/en-US/{board}"

        out = []
        for p in postings:
            posted_on = p.get("postedOn", "")
            days_ago = _parse_posted_on(posted_on)
            external_path = p.get("externalPath", "")
            job_url = base + external_path if external_path else ""

            out.append({
                "id": f"workday_{tenant}_{external_path.strip('/').replace('/', '_')}",
                "company": tenant,
                "title": p.get("title", ""),
                "location": p.get("locationsText", ""),
                "url": job_url,
                "source": self.source_name,
                "timestamp": _days_ago_to_iso(days_ago),
                "days_ago": days_ago,        # raw int for recency filter
                "posted_label": posted_on,   # human-readable label
            })
        return out

    async def fetch_company(
        self, company: str, session: aiohttp.ClientSession
    ) -> List[Dict[str, Any]]:
        """Not used directly — Workday uses fetch_all with config dicts."""
        return []

    async def fetch_all(
        self,
        companies: List[Dict[str, str]],  # list of dicts, not strings
    ) -> List[Dict[str, Any]]:
        sem = asyncio.Semaphore(config.max_concurrent_requests)

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._search_company(c, term, session, sem)
                for c in companies
                for term in _SEARCH_TERMS
            ]
            results = await asyncio.gather(*tasks, return_exceptions=False)

        # Flatten + deduplicate within Workday results by URL
        seen_urls = set()
        unique = []
        for batch in results:
            for job in batch:
                url = job.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique.append(job)
        return unique
