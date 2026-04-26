"""Standalone background polling daemon.

Run independently of Streamlit:
    python runner.py

Logs to stdout. Press Ctrl-C to stop.
"""
import asyncio
import logging
import signal
import sys

from core.aggregator import run_fetch_cycle
from utils.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("runner")

_shutdown = asyncio.Event()


def _on_signal(sig, _frame):
    logger.info("Signal %s received — shutting down after current cycle.", sig)
    _shutdown.set()


async def main() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _on_signal, sig, None)

    logger.info(
        "Job Intelligence daemon started | poll_interval=%ds | sources: GH=%d LV=%d",
        config.poll_interval,
        len(config.greenhouse_companies),
        len(config.lever_companies),
    )

    while not _shutdown.is_set():
        try:
            new_jobs = await run_fetch_cycle()
            logger.info("✓ Cycle complete — %d new job(s) found.", len(new_jobs))
        except Exception as exc:
            logger.error("Cycle failed (will retry next interval): %s", exc, exc_info=True)

        try:
            await asyncio.wait_for(
                _shutdown.wait(), timeout=config.poll_interval
            )
        except asyncio.TimeoutError:
            pass   # normal — just means time to poll again

    logger.info("Daemon stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
