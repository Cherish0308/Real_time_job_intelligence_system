"""Central configuration — all tunables live here."""
import os
from dataclasses import dataclass, field
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Config:
    # ── Job targeting ──────────────────────────────────────────────────────────
    target_titles: List[str] = field(default_factory=lambda: [
        "data scientist",
        "machine learning",
        "ml engineer",
        "ai engineer",
        "data engineer",
        "research scientist",
        "applied scientist",
        "llm engineer",
        "nlp engineer",
    ])

    target_locations: List[str] = field(default_factory=lambda: [
        "united states",
        "usa",
        " us ",         # space-padded to avoid "campus", "focus", etc.
        "remote",
        "new york",
        "san francisco",
        "seattle",
        "austin",
        "boston",
        "chicago",
        "los angeles",
        "denver",
        "atlanta",
    ])

    # ── Greenhouse company slugs ───────────────────────────────────────────────
    greenhouse_companies: List[str] = field(default_factory=lambda: [
        "anthropic",
        "stripe",
        "airbnb",
        "dropbox",
        "figma",
        "brex",
        "notion",
        "airtable",
        "gusto",
        "asana",
        "robinhood",
        "coinbase",
        "databricks",
        "snowflake",
        "confluent",
        "mongodb",
        "hashicorp",
        "zendesk",
        "intercom",
        "squarespace",
        "doordash",
        "instacart",
        "lyft",
        "waymo",
        "scale",
        "weights-and-biases",
        "huggingface",
    ])

    # ── Lever company slugs ────────────────────────────────────────────────────
    lever_companies: List[str] = field(default_factory=lambda: [
        "netflix",
        "duolingo",
        "reddit",
        "pinterest",
        "atlassian",
        "hubspot",
        "twilio",
        "plaid",
        "figma",
        "canva",
        "amplitude",
        "mixpanel",
        "segment",
        "dbt-labs",
        "datadog",
        "grafana",
        "samsara",
    ])

    # ── Polling & storage ──────────────────────────────────────────────────────
    poll_interval: int = 60          # seconds between fetch cycles
    max_job_age_hours: int = 48      # prune jobs older than this
    storage_file: str = "jobs.json"
    max_concurrent_requests: int = 25
    request_timeout: int = 15        # per-request timeout in seconds

    # ── Experience level keywords ──────────────────────────────────────────────
    senior_keywords: List[str] = field(default_factory=lambda: [
        "senior", "sr.", "sr ", "staff", "principal", "lead", "head of",
        "director", "vp ", "vice president", "distinguished", "architect",
    ])

    mid_entry_keywords: List[str] = field(default_factory=lambda: [
        "junior", "jr.", "jr ", "associate", "entry", "mid-level", "mid level",
        "early career", "new grad", "university grad",
    ])

    # ── Alerts ─────────────────────────────────────────────────────────────────
    slack_webhook_url: str = field(
        default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", "")
    )


config = Config()
