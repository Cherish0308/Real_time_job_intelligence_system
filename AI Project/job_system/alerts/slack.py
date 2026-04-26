"""Slack webhook alerting with console fallback."""
import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict

from utils.config import config

logger = logging.getLogger(__name__)

_DIVIDER = "─" * 60


def _format(job: Dict[str, Any]) -> str:
    company = job.get("company", "").replace("-", " ").title()
    location = job.get("location") or "Location not specified"
    return (
        f"🔥 NEW JOB: {job['title']} at {company}\n"
        f"📍 Location: {location}\n"
        f"🔗 Apply: {job['url']}"
    )


def _send_slack(message: str) -> bool:
    if not config.slack_webhook_url:
        return False
    payload = json.dumps({"text": message}).encode("utf-8")
    req = urllib.request.Request(
        config.slack_webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.URLError as exc:
        logger.warning("Slack delivery failed: %s", exc)
        return False


def send_alert(job: Dict[str, Any]) -> None:
    """Alert via Slack; fall back to stdout if webhook not configured."""
    message = _format(job)
    sent = _send_slack(message)
    if not sent:
        print(f"\n{_DIVIDER}\n{message}\n{_DIVIDER}")
