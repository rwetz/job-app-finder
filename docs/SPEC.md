---
type: project
status: planning     # idea → planning → building → shipped → archived
priority: high
started: 2026-07-07
tags:
  - project
  - domain/data
  - domain/ai-ml
  - job-search
  - scraping
stack: [python, sqlite, streamlit, httpx, playwright, apscheduler, sentence-transformers]
repo:
---

# Job Application Finder

> [!abstract] One-liner
> A local tool that pulls as many internship / co-op / job postings as possible from across the web every time I open it, ranks them **local & in-person first** (Fargo, ND ↔ Rochester, MN), then remote, and scores each against my [[Resume]] — so I spend time applying, not searching.

## 🎯 Problem & Motivation

- **Problem:** Job/internship hunting means checking dozens of boards and ATS portals, re-reading the same listings, and manually guessing which fit and which are actually near me. Slow, and easy to miss fresh postings.
- **Why me / why now:** I'm actively looking. This solves my own problem *and* is a portfolio piece showing scraping, API integration, geo-ranking, and AI matching to the employers I'm applying to.
- **Who it's for:** Me (single-user). Anchored to my two locations.

## 📋 Requirements (kickoff decisions — 2026-07-07)

- **Coverage:** Maximize job count. Pull from as many sources as feasible and **dedupe** across them.
- **Freshness:** As up-to-date as possible *every* time I use it → **live fetch on open** + **background scheduled refresh** so it's warm. Show "fetched N min ago" and flag stale/removed postings.
- **Location priority (ranking, not exclusion):** in-person/on-site near an anchor **first**, then hybrid near an anchor, then remote, then on-site far away (would need relocation) last. Remote is welcome — just below local.
- **Anchors:** **Fargo, ND (58102)** and **Rochester, MN (55901)**, weighted equally. Distance measured to the *nearest* anchor.
- **Source strategy:** **Compliant-first.** Build the reliable public-API backbone first; add ToS-risky sources (Handshake, LinkedIn) as optional, flagged, best-effort adapters. I have a **school Handshake login** available for an authenticated session.
- **Runs:** Locally, with a background scheduler.

## ✅ Goals & Non-Goals

**Goals**
- [ ] Aggregate postings from many sources into one deduped list, refreshed live.
- [ ] Rank by location tier → resume match → freshness, with a visible rationale.
- [ ] Filter (tier, remote, keyword, source, min-match) and track status (`interested / applied / rejected`).

**Non-Goals (v1)**
- Auto-applying / auto-submitting.
- Cover-letter or resume generation (possible v2).
- Multi-user accounts (single-user, just me).

## 🧩 Core Features (MVP)

1. **Ingest** — pluggable source adapters (aggregators + ATS APIs) fetched concurrently, normalized to one schema.
2. **Locate** — geocode each posting, classify remote/hybrid/on-site, compute distance to nearest anchor → **location tier**.
3. **Match** — score each posting vs. resume (local embeddings + keyword), LLM rationale for the top matches.
4. **Rank & review** — composite sort (tier → match → freshness); dashboard with filters + status tracking + "Refresh now".

## 🌍 Location & Ranking Model

**Location tiers** (primary sort key — lower is better):

| Tier | Meaning | Rule of thumb |
| --- | --- | --- |
| **0 — Local on-site** | On-site/hybrid within commuting range of an anchor | ≤ ~60 mi of Fargo *or* Rochester |
| **1 — Regional** | On-site within a drivable/relocatable regional band | ≤ ~150 mi of an anchor |
| **2 — Remote** | Remote and eligible for my region (US / role-open) | `remote == true` |
| **3 — Far on-site** | On-site/hybrid, not near an anchor | everything else |

**Composite ranking:** `sort by (location_tier ASC, match_score DESC, posted_at DESC)`, with a small **source-priority** weight as a tiebreaker. Everything is *ingested* (max coverage); tiers only affect ordering and default filters — I can always expand to Tier 3.

## 🛰️ Sources

> Compliant-first. **Backbone = reliable public JSON/RSS** (build these first). **Best-effort = ToS-risky, flagged off by default.**

### Backbone — build first

| Source | Type | Why it's here | Notes |
| --- | --- | --- | --- |
| **Adzuna API** | Aggregator | Free API with **geo radius search** — ideal for "near Fargo/Rochester" | Free app key; broad coverage |
| **JSearch (RapidAPI)** | Aggregator | Compliant way to capture **LinkedIn / Indeed / Glassdoor / ZipRecruiter**-listed jobs | Freemium key |
| **USAJobs API** | Aggregator | Federal jobs, free, geo-aware | Free key |
| **Greenhouse Job Board API** | ATS | Clean public JSON per company | Needs company tokens (see `companies.yaml`) |
| **Lever Postings API** | ATS | Clean public JSON per company | Needs company handles |
| **Workday (CxS)** | ATS | Many big employers; public `/wday/cxs/.../jobs` JSON | Per-tenant; the "APIs like Workday" you asked for |
| **Ashby / SmartRecruiters / Workable / Recruitee** | ATS | More public posting APIs to widen employer coverage | Add as adapters over time |
| **Remotive / RemoteOK / Arbeitnow / WeWorkRemotely** | Remote boards | Free APIs/RSS for the remote tier | Feed Tier 2 |

### Best-effort — behind a flag (personal use, ToS-aware)

| Source | Approach | Caveat |
| --- | --- | --- |
| **Handshake** | Authenticated session using **my school login** (cookie import or Playwright login) | School-gated; respect ToS & rate limits; may break on UI changes |
| **LinkedIn** | Prefer **via JSearch** (compliant). Direct scraping only behind an explicit flag | LinkedIn actively blocks/litigates scraping — discouraged; off by default |

> [!warning] Legality
> Obey each source's `robots.txt`, ToS, and rate limits. Prefer official/aggregator APIs. Best-effort adapters are single-user, low-rate, and opt-in. Never commit credentials.

**Coverage strategy:** aggregators (Adzuna/JSearch/USAJobs) give **breadth** with geo search and no per-company setup; ATS adapters give **depth + freshness** on a curated `companies.yaml` of employers near my anchors (e.g. Rochester: Mayo Clinic, IBM Rochester, Benchmark; Fargo: Microsoft, John Deere, Doosan Bobcat, RDO, Border States, Bell Bank, Sanford Health). Together = max jobs.

## 🛠️ Tech Stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Language | Python | Best scraping + AI ecosystem |
| Fetching | `httpx` (async) + `Playwright` | Async for parallel API pulls; Playwright only for JS/auth (Handshake) |
| Parsing | `BeautifulSoup` / `selectolax` | For any HTML sources |
| Storage | **SQLite** | Local-first, zero-cost; stores postings, applications, sources, fetch runs |
| Geocoding | Offline US zip/city dataset (e.g. `uszipcode`) + Nominatim fallback | Distance to anchors without paid API |
| Matching | `sentence-transformers` (local embeddings) + keyword; **optional Claude** pass for top-N rationale | Local embeddings keep bulk scoring free; LLM only on shortlist |
| Scheduler | `APScheduler` | Background refresh so data is warm |
| Frontend | **Streamlit** | Fastest path to a filterable local dashboard |
| Config/secrets | `.env` + `config.yaml` + `companies.yaml` | Anchors, radii, seed queries, keys, employer tokens |

## 🗺️ Milestones

- [ ] **M1 — Skeleton + breadth:** config/anchors, SQLite schema, source-adapter interface; wire **Adzuna + JSearch + USAJobs** with geo search around both anchors → store deduped postings.
- [ ] **M2 — Locate + rank:** geocode, assign location tiers, composite ranking; basic Streamlit list sorted local-first.
- [ ] **M3 — Depth (ATS):** Greenhouse + Lever + Workday adapters driven by `companies.yaml`; add remote-board adapters.
- [ ] **M4 — Match:** local-embedding + keyword scoring, optional Claude rationale on the shortlist.
- [ ] **M5 — Fresh + usable:** APScheduler background refresh, "fetched N min ago", filters, apply-status tracking, stale/removed flags.
- [ ] **M6 — Handshake (flagged):** authenticated best-effort adapter using my school session.

## 🤖 Claude Code Brief

> [!note] Paste this section into Claude Code to start building.

**Objective:** Build a single-user, local Python app that aggregates as many job/internship/co-op postings as possible from many sources on every run, dedupes them, geocodes and tiers them by proximity to two anchor cities (**Fargo, ND** and **Rochester, MN**), scores each against my resume, and presents a filterable dashboard ranked **local/in-person → remote → far**, with application-status tracking and background refresh.

**Stack & constraints:**
- Python. Async `httpx` for API pulls; `Playwright` only where auth/JS is required. SQLite storage. Streamlit UI. APScheduler for background refresh.
- **Compliant-first:** obey `robots.txt`, ToS, rate limits; prefer official/aggregator APIs. Best-effort adapters (Handshake, LinkedIn-direct) live behind config flags, **default off**, low-rate, single-user.
- Secrets in `.env` (git-ignored); employer/ATS tokens in `companies.yaml`; anchors/radii/queries in `config.yaml`. Ship `.env.example`.

**Architecture:**
- **Source adapter interface** — each source implements `fetch(queries, anchors) -> list[Posting]`; register in a registry with metadata `{name, kind: aggregator|ats|board|besteffort, priority, requires_auth, tos_risk}`.
- **Normalized `Posting`** — `source, external_id, title, company, location_raw, lat, lon, is_remote, url(canonical), description, posted_at, fetched_at`.
- **Dedup** — canonicalize URL + fuzzy key on `(normalized company + title + location)`; keep earliest `posted_at`, merge sources.
- **Geo/tiering** — geocode `location_raw`; compute distance to nearest anchor; set `location_tier ∈ {0,1,2,3}` per the Location & Ranking Model.
- **Match** — load resume from [[Resume]]; local-embedding similarity + keyword hits → `match_score`; optional Claude pass returns `{score, one-line rationale}` for the top N only.
- **Rank** — `ORDER BY location_tier ASC, match_score DESC, posted_at DESC`, source-priority tiebreak.

**Build order (verify each before moving on):**
1. **Scaffold** — repo, deps, `config.yaml`/`companies.yaml`/`.env.example`, SQLite schema (`postings`, `applications(posting_id,status,notes)`, `sources`, `fetch_runs`), adapter interface + registry, hello-world run.
2. **Aggregators** — implement **Adzuna, JSearch, USAJobs** with geo radius around both anchors + seed queries; normalize, dedupe, upsert; log per-source counts.
3. **Geo + tiering** — geocoding + `location_tier`; unit-test with known cities (Fargo, Rochester, remote, Seattle).
4. **UI v1** — Streamlit list ranked local-first with filters (tier, remote, keyword, source) and status buttons.
5. **ATS depth** — Greenhouse, Lever, Workday adapters from `companies.yaml` (seed with employers near the anchors); add remote boards (Remotive/RemoteOK).
6. **Match** — local embeddings + keyword scoring; optional Claude rationale on the shortlist; store results.
7. **Freshness** — APScheduler background refresh + live fetch on open; "fetched N min ago"; mark postings not seen in last run as `stale`.
8. **Handshake (flagged)** — authenticated best-effort adapter via my school session (cookie import first; Playwright login fallback), rate-limited, off by default.

**Definition of done for v1:** Opening the app live-fetches across aggregators + ATS around Fargo/Rochester (plus remote), dedupes, geocodes, ranks **local/in-person first**, shows each posting's match score + one-line why + freshness, and lets me mark status — persisted across runs, with a background refresh keeping it current.

**Open questions for me to answer first:**
- **Roles/keywords to seed** the search (e.g. "software engineering intern", "data co-op", level, field)? — pull from [[Resume]] once it's filled in.
- **Employer seed list** — confirm/extend the `companies.yaml` targets near each anchor.
- **API keys** — OK to grab free keys for **Adzuna**, **JSearch (RapidAPI)**, **USAJobs**? (All have free tiers.)
- **Matching** — OK with **local embeddings** for bulk scoring + **optional Claude API** only for the shortlist rationale (keeps it ~free)?
- **Handshake** — capture session via cookie import or a Playwright login? Confirm comfort with personal-use ToS.

## 📓 Log & Decisions

- `2026-07-07` — Kickoff decisions locked: compliant-first sourcing, dual anchors (Fargo/Rochester) with local-first ranking, max coverage + live/scheduled freshness, local app, Handshake behind a flag (school login available). Stack chosen. Spec expanded with source tiers, geo model, and build order.
- `2026-07-07` — Created and scoped.

## 🔗 Related
- [[Resume]] — matching source of truth (fill in to seed roles/keywords)
- [[Idea Backlog]] · [[Idea Generation Framework]] · [[Project Types Catalog]] · [[Home]]
