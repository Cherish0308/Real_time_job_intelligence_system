"""Streamlit dashboard — Real-Time Data Jobs (US).

Background fetch loop runs in a daemon thread via @st.cache_resource —
starts once per server process, shared across all users.
"""
import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import streamlit as st

from core.aggregator import run_fetch_cycle
from core.filter import is_recent
from core.storage import load_jobs
from utils.config import config

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


def _recency_label(job: Dict[str, Any]) -> str:
    """Human-readable recency: prefer Workday's label, fall back to time_ago."""
    label = job.get("posted_label", "")
    if label:
        return label          # e.g. "Posted Today", "Posted 2 Days Ago"
    return _time_ago(job.get("timestamp", ""))


def _rank(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remote first → newest first."""
    def _score(job):
        is_remote = "remote" in job.get("location", "").lower()
        days = job.get("days_ago")
        if days is not None:
            age_minutes = days * 1440
        else:
            try:
                ts = datetime.fromisoformat(job["timestamp"].replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_minutes = (datetime.now(timezone.utc) - ts).total_seconds() / 60
            except Exception:
                age_minutes = 99999
        return (not is_remote, age_minutes)

    return sorted(jobs, key=_score)


def _prettify(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


# ── Sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.title("🔍 Filters")

keyword = st.sidebar.text_input(
    "Keyword search", placeholder="e.g. NLP, LLM, Spark …"
).strip().lower()

all_companies = sorted(set(
    config.greenhouse_companies
    + config.lever_companies
    + [c["tenant"] for c in config.workday_companies]
))
selected_companies = st.sidebar.multiselect(
    "Company", options=all_companies, format_func=_prettify
)

selected_source = st.sidebar.selectbox(
    "Source", ["All", "greenhouse", "lever", "workday"]
)

exp_options = ["All", "0-5 years (Entry / Mid)", "5+ years (Senior / Staff / Lead)"]
selected_exp = st.sidebar.selectbox("Experience Level", exp_options)

st.sidebar.divider()
st.sidebar.subheader("⏱ Recency")
only_recent = st.sidebar.checkbox(
    f"Only show jobs posted ≤ {config.recent_days} days ago", value=True
)
max_days_override = st.sidebar.slider(
    "Max days old", min_value=1, max_value=14,
    value=config.recent_days, disabled=not only_recent
)

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
    f"Showing jobs ≤ **{max_days_override if only_recent else config.max_job_age_hours // 24} days** old · "
    f"Sources: Greenhouse + Lever + Workday"
)

# ── Load + filter ──────────────────────────────────────────────────────────────

all_jobs = load_jobs()
ranked = _rank(all_jobs)

# Recency filter
if only_recent:
    ranked = [j for j in ranked if is_recent(j, max_days=max_days_override)]

# Keyword
if keyword:
    ranked = [
        j for j in ranked
        if keyword in j.get("title", "").lower()
        or keyword in j.get("company", "").lower()
        or keyword in j.get("location", "").lower()
    ]

# Company
if selected_companies:
    ranked = [j for j in ranked if j.get("company") in selected_companies]

# Source
if selected_source != "All":
    ranked = [j for j in ranked if j.get("source") == selected_source]

# Experience level
if selected_exp == "0-5 years (Entry / Mid)":
    ranked = [j for j in ranked if j.get("experience_level") in ("0-5", "any")]
elif selected_exp == "5+ years (Senior / Staff / Lead)":
    ranked = [j for j in ranked if j.get("experience_level") in ("5+", "any")]

# ── Metrics ────────────────────────────────────────────────────────────────────

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Matches", len(ranked))
c2.metric("🌐 Remote", sum(1 for j in ranked if "remote" in j.get("location", "").lower()))
c3.metric("🔵 Senior (5+)", sum(1 for j in ranked if j.get("experience_level") == "5+"))
c4.metric("🟢 Entry/Mid (0-5)", sum(1 for j in ranked if j.get("experience_level") == "0-5"))
c5.metric("📅 Posted Today", sum(1 for j in ranked if j.get("days_ago") == 0 or _time_ago(j.get("timestamp","")) in ("just now",)))

st.divider()

# ── Job cards ──────────────────────────────────────────────────────────────────

if not ranked:
    st.info(
        "No recent jobs found matching your filters. "
        "Try increasing 'Max days old' in the sidebar, or uncheck the recency filter.",
        icon="⏳",
    )
else:
    for job in ranked:
        location     = job.get("location") or "Location not specified"
        is_remote    = "remote" in location.lower()
        remote_tag   = " &nbsp;`🌐 Remote`" if is_remote else ""
        company_disp = _prettify(job.get("company", ""))
        source_badge = f"`{job.get('source', '')}`"
        posted       = _recency_label(job)
        days         = job.get("days_ago")

        # Recency colour: green = today, yellow = 1-2d, grey = older
        if days == 0:
            recency_color = "🟢"
        elif days is not None and days <= 2:
            recency_color = "🟡"
        else:
            recency_color = "⚪"

        exp = job.get("experience_level", "any")
        exp_badge = (
            " &nbsp;`🟢 0–5 yrs`" if exp == "0-5"
            else " &nbsp;`🔵 5+ yrs`" if exp == "5+"
            else ""
        )

        with st.container():
            left, right = st.columns([5, 1])
            with left:
                st.markdown(
                    f"### [{job.get('title', 'Untitled')}]({job.get('url', '#')})"
                    f"{remote_tag}{exp_badge}",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**{company_disp}** &nbsp;·&nbsp; 📍 {location} &nbsp;·&nbsp; {source_badge}",
                    unsafe_allow_html=True,
                )
            with right:
                st.markdown(f"{recency_color} *{posted}*")
                st.link_button("Apply →", job.get("url", "#"), use_container_width=True)

        st.divider()

# ── Auto-refresh ───────────────────────────────────────────────────────────────

if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
