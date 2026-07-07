"""Shared presentation constants and small render helpers for app.py.

Theming (colors, fonts, radii) lives in .streamlit/config.toml — this module
only adds the bits Streamlit's theme system can't express: semantic
label/icon/color lookups and the handful of CSS rules needed for motion.
"""

TIER_META = {
    0: {"label": "Local on-site", "short": "Tier 0", "color": "green", "icon": ":material/location_on:"},
    1: {"label": "Regional", "short": "Tier 1", "color": "blue", "icon": ":material/map:"},
    2: {"label": "Remote-friendly", "short": "Tier 2", "color": "violet", "icon": ":material/wifi:"},
    3: {"label": "Far on-site", "short": "Tier 3", "color": "orange", "icon": ":material/flight_takeoff:"},
}

STATUS_ORDER = ["interested", "applied", "rejected"]
STATUS_META = {
    "interested": {"label": "Interested", "emoji": "⭐"},
    "applied": {"label": "Applied", "emoji": "📨"},
    "rejected": {"label": "Rejected", "emoji": "🚫"},
}

# is_stale can come from two different signals (see link_check.py) — a direct
# URL check is much stronger evidence than "didn't reappear in a refresh", so
# they get visually distinct badges rather than one ambiguous "Stale".
STALE_META = {
    "link_check": {"label": "Confirmed offline", "color": "red", "icon": ":material/link_off:"},
    "not_seen": {"label": "Possibly stale", "color": "gray", "icon": ":material/schedule:"},
}
DEFAULT_STALE_META = STALE_META["not_seen"]


def tier_pill_label(tier: int) -> str:
    meta = TIER_META.get(tier)
    if meta is None:
        return f"Tier {tier}"
    return f"{meta['short']} · {meta['label']}"


def status_option_label(status: str) -> str:
    meta = STATUS_META[status]
    return f"{meta['emoji']} {meta['label']}"


def stale_meta(stale_reason: str | None) -> dict:
    return STALE_META.get(stale_reason, DEFAULT_STALE_META)


def match_badge(score: float) -> tuple[str, str]:
    """Return (color, display text) for a 0-1 match score."""
    if score >= 0.7:
        return "green", f"Match {score:.0%}"
    if score >= 0.4:
        return "orange", f"Match {score:.0%}"
    return "gray", f"Match {score:.0%}"


# Only motion/interaction rules here — colors, fonts, and radii belong in
# .streamlit/config.toml so the theme survives Streamlit upgrades.
ANIMATION_CSS = """
<style>
@keyframes fadeSlideIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

div[class*="st-key-card-"] {
  animation: fadeSlideIn 0.32s ease both;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
}
div[class*="st-key-card-"]:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(20, 20, 40, 0.10);
}

div[class*="st-key-stat-"] {
  transition: transform 0.16s ease, box-shadow 0.16s ease;
}
div[class*="st-key-stat-"]:hover {
  transform: translateY(-2px);
}

button {
  transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease !important;
}
button:hover {
  transform: translateY(-1px);
  filter: brightness(1.03);
}
button:active {
  transform: translateY(0);
}

[data-testid="stMarkdownBadge"] {
  transition: transform 0.12s ease;
}
[data-testid="stMarkdownBadge"]:hover {
  transform: scale(1.06);
}

[data-testid="stSpinner"] {
  animation: fadeSlideIn 0.2s ease both;
}
</style>
"""
