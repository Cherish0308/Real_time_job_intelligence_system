"""Streamlit dashboard — Real-Time Data Jobs (US).

The background fetch loop runs in a daemon thread managed by
`@st.cache_resource` so it starts once per server process, not per user.
"""
import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import streamlit as st

from core.aggregator import run_fetch_cycle
from core.storage import load_jobs
from utils.config import config

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Real-Time Data Jobs (US)",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

logger = logging.getLogger(__name__)

# ── Background fetch loop ──────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _start_background_loop() -> threading.Thread:
    """Starts exactly one daemon thread per Streamlit server process."""
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while True:
            try:
                loop.run_until_complete(run_fetch_cycle())
            except Exception as exc:
                logger.error("Background cycle error: %s", exc, exc_info=True)
            time.sleep(config.poll_interval)

    thread = threading.Thread(target=_run, name="job-fetch-loop", daemon=True)
    thread.start()
    return thread


_start_background_loop()

# ── Helpers ────────────────────────────────────────────────────────────────────

def _time_ago(ts_str: str) -> str:
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        minutes = int(delta.total_seconds() / 60)
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{minutes}m ago"
        if minutes < 1440:
            return f"{minutes // 60}h {minutes % 60}m ago"
        return f"{minutes // 1440}d ago"
    except Exception:
        return "—"


def _rank(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remote jobs first, then newest first."""
    def _score(job):
        is_remote = "remote" in job.get("location", "").lower()
        try:
            ts = datetime.fromisoformat(
                job["timestamp"].replace("Z", "+00:00")
            )
        except Exception:
            ts = datetime.min.replace(tzinfo=timezone.utc)
        return (not is_remote, -ts.timestamp())

    return sorted(jobs, key=_score)


def _prettify_company(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


# ── Sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.title("🔍 Filters")

keyword = st.sidebar.text_input("Keyword search", placeholder="e.g. NLP, LLM, …").strip().lower()

all_companies = sorted(set(config.greenhouse_companies + config.lever_companies))
selected_companies = st.sidebar.multiselect(
    "Company",
    options=all_companies,
    format_func=_prettify_company,
)

selected_source = st.sidebar.selectbox("Source", ["All", "greenhouse", "lever"])

st.sidebar.divider()

refresh_interval = st.sidebar.slider(
    "Auto-refresh (seconds)", min_value=30, max_value=300, value=60, step=15
)
auto_refresh = st.sidebar.checkbox("Auto-refresh enabled", value=True)

if st.sidebar.button("⟳  Refresh now"):
    st.rerun()

# ── Main header ────────────────────────────────────────────────────────────────

st.title("🔍 Real-Time Data Jobs (US)")
st.caption(
    f"Polling every **{config.poll_interval}s** · "
    f"Showing jobs from the last **{config.max_job_age_hours}h** · "
    f"Sources: Greenhouse + Lever"
)

# ── Load + filter ──────────────────────────────────────────────────────────────

all_jobs = load_jobs()
ranked = _rank(all_jobs)

if keyword:
    ranked = [
        j for j in ranked
        if keyword in j.get("title", "").lower()
        or keyword in j.get("company", "").lower()
        or keyword in j.get("location", "").lower()
    ]

if selected_companies:
    ranked = [j for j in ranked if j.get("company") in selected_companies]

if selected_source != "All":
    ranked = [j for j in ranked if j.get("source") == selected_source]

# ── Metrics ────────────────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)
c1.metric("Matching Jobs", len(ranked))
c2.metric("Remote", sum(1 for j in ranked if "remote" in j.get("location", "").lower()))
c3.metric("Greenhouse", sum(1 for j in ranked if j.get("source") == "greenhouse"))
c4.metric("Lever", sum(1 for j in ranked if j.get("source") == "lever"))

st.divider()

# ── Job cards ──────────────────────────────────────────────────────────────────

if not ranked:
    st.info(
        "No jobs match your current filters. "
        "The background loop is running — new jobs will appear automatically.",
        icon="⏳",
    )
else:
    for job in ranked:
        location = job.get("location") or "Location not specified"
        is_remote = "remote" in location.lower()
        remote_tag = " &nbsp;`🌐 Remote`" if is_remote else ""
        company_display = _prettify_company(job.get("company", ""))
        source_badge = f"`{job.get('source', '')}`"
        posted = _time_ago(job.get("timestamp", ""))

        with st.container():
            left, right = st.columns([5, 1])
            with left:
                st.markdown(
                    f"### [{job.get('title', 'Untitled')}]({job.get('url', '#')}){remote_tag}",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**{company_display}** &nbsp;·&nbsp; 📍 {location} &nbsp;·&nbsp; {source_badge}",
                    unsafe_allow_html=True,
                )
            with right:
                st.markdown(f"&nbsp;")
                st.markdown(f"⏱ *{posted}*")
                st.link_button("Apply →", job.get("url", "#"), use_container_width=True)

        st.divider()

# ── Auto-refresh ───────────────────────────────────────────────────────────────

if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
