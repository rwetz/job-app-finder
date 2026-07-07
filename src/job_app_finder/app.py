import streamlit as st

from job_app_finder.config import load_config
from job_app_finder.db.database import init_db
from job_app_finder.db.queries import distinct_sources, last_refresh_at, list_postings, set_application_status
from job_app_finder.humanize import is_stale, minutes_ago
from job_app_finder.ingest import run_ingest_sync
from job_app_finder.sources.base import get_registry
from job_app_finder.ui import (
    ANIMATION_CSS,
    STATUS_ORDER,
    TIER_META,
    match_badge,
    stale_meta,
    status_option_label,
    tier_pill_label,
)

st.set_page_config(page_title="Job Application Finder", page_icon=":material/work:", layout="wide")
st.html(ANIMATION_CSS)

config = load_config()
conn = init_db(config.db_path)


@st.cache_resource
def _background_scheduler(interval_minutes: int):
    from job_app_finder.scheduler import start_background_scheduler

    try:
        return start_background_scheduler(interval_minutes)
    except ImportError:
        return None


scheduler = _background_scheduler(config.refresh_interval_minutes)

if is_stale(last_refresh_at(conn), config.refresh_interval_minutes):
    with st.spinner("Fetching latest postings…"):
        run_ingest_sync(config, conn)

st.title(":material/work: Job application finder")
st.caption(
    "Ranked local-first (Fargo, ND / Rochester, MN), then remote, then far away. "
    f"Last refreshed {minutes_ago(last_refresh_at(conn))}."
)
if scheduler is None:
    st.sidebar.caption(
        "Background refresh disabled — `pip install -e \".[schedule]\"` to keep data warm between opens."
    )

with st.sidebar:
    st.header(":material/tune: Filters", divider="gray")
    tier_selection = st.pills(
        "Location tier",
        options=list(TIER_META),
        format_func=tier_pill_label,
        selection_mode="multi",
    )
    remote_only = st.toggle(":material/wifi: Remote only")
    keyword = st.text_input(":material/search: Keyword", placeholder="e.g. python, data, intern")
    available_sources = distinct_sources(conn)
    source_selection = st.multiselect(":material/dns: Source", options=available_sources, default=[])
    min_match = st.slider(
        ":material/target: Min match score",
        0.0,
        1.0,
        0.0,
        0.05,
        help="0 = no filter, 1 = perfect match",
    )
    include_stale = st.toggle(":material/schedule: Include stale postings", value=True)

    st.space("small")
    if st.button("Refresh now", type="primary", icon=":material/refresh:", width="stretch"):
        with st.spinner("Fetching from all enabled sources…"):
            summary = run_ingest_sync(config, conn)
        for source, stats in summary.items():
            if source == "_meta":
                continue
            if stats["error"]:
                st.error(f"{source}: {stats['error']}", icon=":material/error:")
            else:
                st.success(f"{source}: {stats['fetched']} fetched, {stats['new']} new", icon=":material/check_circle:")
        meta = summary.get("_meta", {})
        if meta.get("link_checked"):
            st.caption(
                f":material/link: Checked {meta['link_checked']} listing link(s) · "
                f"{meta['link_confirmed_offline']} confirmed offline"
            )
        st.rerun()

    with st.expander("Registered sources", icon=":material/dns:"):
        registry = get_registry()
        active_sources = set(config.enabled_sources) | set(config.besteffort_enabled)
        for name, adapter in sorted(registry.items()):
            active = name in active_sources
            with st.container(horizontal=True, vertical_alignment="center"):
                st.badge(
                    name,
                    color="green" if active else "gray",
                    icon=":material/check_circle:" if active else ":material/radio_button_unchecked:",
                )
                st.caption(adapter.meta.kind)

postings = list_postings(
    conn,
    tiers=tier_selection or None,
    remote_only=remote_only,
    keyword=keyword or None,
    sources=source_selection or None,
    min_match=min_match if min_match > 0 else None,
    include_stale=include_stale,
)

scored = [p["match_score"] for p in postings if p["match_score"] is not None]
stats = {
    "total": len(postings),
    "tier0": sum(1 for p in postings if p["location_tier"] == 0),
    "remote": sum(1 for p in postings if p["is_remote"]),
    "avg_match": (sum(scored) / len(scored)) if scored else None,
}

with st.container(horizontal=True):
    with st.container(key="stat-total"):
        st.metric("Showing", stats["total"], border=True)
    with st.container(key="stat-tier0"):
        st.metric("Tier 0 · local", stats["tier0"], border=True)
    with st.container(key="stat-remote"):
        st.metric("Remote", stats["remote"], border=True)
    with st.container(key="stat-match"):
        st.metric(
            "Avg match",
            f"{stats['avg_match']:.0%}" if stats["avg_match"] is not None else "—",
            border=True,
        )

st.space("small")

list_col, sort_col = st.columns([3, 1], vertical_alignment="bottom")
with list_col:
    st.subheader(f"Postings ({len(postings)})")
with sort_col:
    sort_choice = st.selectbox(
        "Sort by",
        ["Best match", "Newest first", "Company A–Z"],
        label_visibility="collapsed",
    )

if sort_choice == "Newest first":
    postings = sorted(postings, key=lambda p: p["posted_at"] or "", reverse=True)
elif sort_choice == "Company A–Z":
    postings = sorted(postings, key=lambda p: (p["company"] or "").lower())

if not postings:
    st.info("No postings match these filters. Try Refresh now, or widen the filters.", icon=":material/search_off:")

for posting in postings:
    with st.container(border=True, key=f"card-{posting['id']}"):
        title_col, status_col = st.columns([3, 2], vertical_alignment="center")

        with title_col:
            st.markdown(f"**[{posting['title']}]({posting['url']})**  ·  {posting['company']}")

            with st.container(horizontal=True):
                tier = posting["location_tier"]
                tier_meta = TIER_META.get(tier)
                if tier_meta:
                    st.badge(tier_meta["short"], color=tier_meta["color"], icon=tier_meta["icon"])
                if posting["is_remote"]:
                    st.badge("Remote", color="violet", icon=":material/wifi:")
                if posting["match_score"] is not None:
                    color, text = match_badge(posting["match_score"])
                    st.badge(text, color=color, icon=":material/target:")
                if posting["is_stale"]:
                    meta = stale_meta(posting["stale_reason"])
                    st.badge(meta["label"], color=meta["color"], icon=meta["icon"])

            st.caption(
                f"{posting['location_raw'] or 'Location unknown'}  ·  "
                f"fetched {minutes_ago(posting['fetched_at'])}  ·  sources: {posting['merged_sources']}"
            )
            if posting["match_rationale"]:
                st.caption(f":material/lightbulb: {posting['match_rationale']}")

        with status_col:
            current = posting["application_status"]
            selection = st.segmented_control(
                "Application status",
                options=STATUS_ORDER,
                format_func=status_option_label,
                default=current if current in STATUS_ORDER else None,
                required=True,
                key=f"status-{posting['id']}",
                label_visibility="collapsed",
            )
            if selection is not None and selection != current:
                set_application_status(conn, posting["id"], selection)
                st.rerun()
