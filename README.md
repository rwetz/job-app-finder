# Job Application Finder

Local-first job/internship aggregator. Pulls postings from many sources, dedupes
them, ranks **local & in-person first** (Fargo, ND ↔ Rochester, MN), then
remote, then far — scored against a resume. See `Job Application Finder.md`
for the full spec and Location & Ranking Model.

All six milestones (M1–M6) from the spec are implemented:

- **M1/M2 — Ingest + rank:** Adzuna, JSearch, USAJobs (aggregators) wired up;
  canonicalize-URL + fuzzy-key dedup with source merging; geocoding
  (uszipcode + Nominatim, cached) and 0–3 location tiering; ranked Streamlit
  dashboard with tier/remote/keyword/source/match filters and
  interested/applied/rejected status tracking.
- **M3 — Depth:** Greenhouse, Lever, Workday ATS adapters driven by
  `companies.yaml`; Remotive + RemoteOK remote-board adapters.
- **M4 — Match:** local sentence-transformer embeddings + keyword overlap for
  bulk scoring (free); optional Claude pass for a one-line rationale on the
  match-score shortlist only.
- **M5 — Freshness:** APScheduler background refresh (keeps data warm even
  when the app isn't open) + live fetch on open + "fetched N min ago" +
  stale-posting flags. Staleness comes from two signals: a passive
  not-seen-in-a-refresh check, and an active link check that GETs each
  posting's own URL looking for a 404 or a closed-job page — the UI badges
  these differently ("Possibly stale" vs "Confirmed offline").
- **M6 — Handshake (flagged):** cookie-session best-effort adapter, off by
  default — opt in via `besteffort_enabled` in `config.yaml`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[scrape,geo,match,schedule]"   # everything
pip install -e ".[dev]"                          # pytest

```

Create a `.env` file in the project root (it's git-ignored) with:

```bash
# Adzuna (https://developer.adzuna.com/) — free app key
ADZUNA_APP_ID=
ADZUNA_APP_KEY=

# JSearch (https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) via RapidAPI.
# Paste just the key value (x-rapidapi-key), not the whole example snippet.
RAPIDAPI_KEY=

# USAJobs (https://developer.usajobs.gov/) — requires your email as a User-Agent
USAJOBS_API_KEY=
USAJOBS_USER_AGENT=

# Optional — Claude API, used only for shortlist match rationale (M4)
ANTHROPIC_API_KEY=

# Handshake best-effort adapter (M6, off by default, needs "handshake" added
# to sources.besteffort_enabled in config.yaml too). Log into
# app.joinhandshake.com, open DevTools > Network, copy the raw `Cookie:`
# request header value from any XHR request. Re-capture when it expires.
HANDSHAKE_COOKIE=
```

`config.yaml`'s `refresh` section controls freshness behavior:

```yaml
refresh:
  background_interval_minutes: 30   # background + "is this page stale" threshold
  link_check_enabled: true          # active liveness probe, see M5 above
  link_check_interval_hours: 6      # min hours between re-checking the same posting
```

Adzuna, JSearch, and USAJobs need free API keys (see signup links above).
Without keys those adapters just no-op — Remotive and RemoteOK work with zero
configuration.

## Run

```bash
streamlit run src/job_app_finder/app.py
```

On open: live-fetches from every enabled source, geocodes/tiers new postings,
scores them against `resume.md`, and shows the ranked list. A background
APScheduler job keeps refreshing on `refresh.background_interval_minutes`
(config.yaml) even while you're not looking at the page.

**Fill in `resume.md`** with real resume content — match scores are
meaningless against the placeholder.

## Layout

```
config.yaml           anchors, location tiers, seed queries, enabled sources, match settings
companies.yaml         ATS (Greenhouse/Lever/Workday) targets
.env                     API keys, git-ignored — see Setup above for the vars to fill in
resume.md                match-scoring source of truth — fill this in
.streamlit/config.toml    theme (fonts, colors, radii) for the dashboard
src/job_app_finder/
  config.py               loads config.yaml + companies.yaml + .env
  models.py                Posting / Anchor dataclasses
  dedup.py                  URL canonicalization + fuzzy dedup key
  geo.py                    haversine, geocoding (cached), location tiering
  match.py                  keyword + embedding scoring, Claude shortlist rationale
  ingest.py                 orchestrates all adapters -> dedup/upsert -> tier -> match -> link check
  link_check.py              active URL liveness probe (404 / closed-job page detection)
  scheduler.py               APScheduler background refresh
  humanize.py                 "N min ago" formatting
  db/                          schema, connection, postings repo, ranked-list queries
  sources/                     one module per adapter + base interface/registry
  ui.py                         dashboard presentation constants (badges, colors, animation CSS)
  app.py                        Streamlit entrypoint
tests/                          65 tests — dedup, geo, match, adapters (mocked HTTP), scheduler, link check
```

## Tests

```bash
pytest
```
