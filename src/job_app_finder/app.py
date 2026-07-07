import streamlit as st

from job_app_finder.config import load_config
from job_app_finder.db.database import init_db
from job_app_finder.db.queries import distinct_sources, last_refresh_at, list_postings, set_application_status
from job_app_finder.humanize import is_stale, minutes_ago
from job_app_finder.ingest import run_ingest_sync
from job_app_finder.sources.base import get_registry

TIER_LABELS = {
    0: "Tier 0 — Local on-site",
    1: "Tier 1 — Regional",
    2: "Tier 2 — Remote",
    3: "Tier 3 — Far on-site",
}

st.set_page_config(page_title="Job Application Finder", layout="wide")

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

st.title("Job Application Finder")
st.caption(
    "Ranked local-first (Fargo, ND / Rochester, MN), then remote, then far. "
    f"Last refreshed: {minutes_ago(last_refresh_at(conn))}."
)
if scheduler is None:
    st.sidebar.caption(
        "Background refresh disabled — `pip install -e \".[schedule]\"` to keep data warm between opens."
    )

with st.sidebar:
    st.header("Filters")
    tier_selection = st.multiselect(
        "Location tier",
        options=list(TIER_LABELS),
        format_func=lambda t: TIER_LABELS[t],
        default=[],
    )
    remote_only = st.checkbox("Remote only")
    keyword = st.text_input("Keyword")
    available_sources = distinct_sources(conn)
    source_selection = st.multiselect("Source", options=available_sources, default=[])
    min_match = st.slider("Min match score", 0.0, 1.0, 0.0, 0.05)
    include_stale = st.checkbox("Include stale postings", value=True)

    st.divider()
    if st.button("Refresh now", type="primary"):
        with st.spinner("Fetching from all enabled sources…"):
            summary = run_ingest_sync(config, conn)
        for source, stats in summary.items():
            if source == "_meta":
                continue
            if stats["error"]:
                st.error(f"{source}: {stats['error']}")
            else:
                st.success(f"{source}: {stats['fetched']} fetched, {stats['new']} new")
        st.rerun()

    st.divider()
    st.subheader("Registered sources")
    registry = get_registry()
    for name, adapter in sorted(registry.items()):
        active = name in set(config.enabled_sources) | set(config.besteffort_enabled)
        st.write(f"{'🟢' if active else '⚪'} {name} ({adapter.meta.kind})")

postings = list_postings(
    conn,
    tiers=tier_selection or None,
    remote_only=remote_only,
    keyword=keyword or None,
    sources=source_selection or None,
    min_match=min_match if min_match > 0 else None,
    include_stale=include_stale,
)

st.subheader(f"Postings ({len(postings)})")

if not postings:
    st.info("No postings match these filters. Try Refresh now, or widen the filters.")

for posting in postings:
    with st.container(border=True):
        header_col, status_col = st.columns([4, 2])
        with header_col:
            title_line = f"**[{posting['title']}]({posting['url']})** — {posting['company']}"
            if posting["is_stale"]:
                title_line += " 🕓 stale"
            st.markdown(title_line)
            tier = posting["location_tier"]
            badges = [TIER_LABELS.get(tier, "Tier ?")]
            if posting["is_remote"]:
                badges.append("Remote")
            if posting["match_score"] is not None:
                badges.append(f"Match {posting['match_score']:.0%}")
            st.caption(
                f"{posting['location_raw'] or 'Location unknown'} · {' · '.join(badges)} · "
                f"fetched {minutes_ago(posting['fetched_at'])} · sources: {posting['merged_sources']}"
            )
            if posting["match_rationale"]:
                st.caption(f"💡 {posting['match_rationale']}")

        with status_col:
            current = posting["application_status"]
            btn_cols = st.columns(3)
            for i, status in enumerate(("interested", "applied", "rejected")):
                label = status.capitalize()
                if current == status:
                    label = f"✅ {label}"
                if btn_cols[i].button(label, key=f"{status}-{posting['id']}"):
                    set_application_status(conn, posting["id"], status)
                    st.rerun()
