"""Abstract base fetcher — all sources implement this contract."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import aiohttp


class BaseFetcher(ABC):
    source_name: str = ""

    @abstractmethod
    async def fetch_company(
        self, company: str, session: aiohttp.ClientSession
    ) -> List[Dict[str, Any]]:
        """Fetch and normalize jobs for one company."""

    @abstractmethod
    async def fetch_all(
        self, companies: List[str]
    ) -> List[Dict[str, Any]]:
        """Fetch jobs for all companies concurrently."""
