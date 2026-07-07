-- Job Application Finder — SQLite schema.
-- Tables per the project brief: postings, applications, sources, fetch_runs.

CREATE TABLE IF NOT EXISTS sources (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    kind          TEXT NOT NULL CHECK (kind IN ('aggregator', 'ats', 'board', 'besteffort')),
    priority      INTEGER NOT NULL DEFAULT 0,
    requires_auth INTEGER NOT NULL DEFAULT 0,
    tos_risk      TEXT NOT NULL DEFAULT 'none' CHECK (tos_risk IN ('none', 'low', 'medium', 'high')),
    enabled       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS postings (
    id               INTEGER PRIMARY KEY,
    source           TEXT NOT NULL,
    external_id      TEXT NOT NULL,
    title            TEXT NOT NULL,
    company          TEXT NOT NULL,
    location_raw     TEXT,
    lat              REAL,
    lon              REAL,
    is_remote        INTEGER NOT NULL DEFAULT 0,
    url              TEXT NOT NULL UNIQUE,
    description      TEXT,
    posted_at        TEXT,
    fetched_at       TEXT NOT NULL,
    dedup_key        TEXT,
    merged_sources   TEXT,
    last_seen_at     TEXT,
    location_tier    INTEGER CHECK (location_tier IN (0, 1, 2, 3)),
    match_score      REAL,
    match_rationale  TEXT,
    is_stale         INTEGER NOT NULL DEFAULT 0,
    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_postings_dedup_key ON postings (dedup_key);
CREATE INDEX IF NOT EXISTS idx_postings_ranking ON postings (location_tier, match_score, posted_at);

CREATE TABLE IF NOT EXISTS applications (
    id         INTEGER PRIMARY KEY,
    posting_id INTEGER NOT NULL REFERENCES postings (id) ON DELETE CASCADE,
    status     TEXT NOT NULL DEFAULT 'interested' CHECK (status IN ('interested', 'applied', 'rejected')),
    notes      TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE (posting_id)
);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id            INTEGER PRIMARY KEY,
    source        TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    count_fetched INTEGER NOT NULL DEFAULT 0,
    count_new     INTEGER NOT NULL DEFAULT 0,
    count_updated INTEGER NOT NULL DEFAULT 0,
    error         TEXT
);

-- Cache of geocoded locations so repeated refreshes don't re-hit Nominatim.
CREATE TABLE IF NOT EXISTS geocode_cache (
    location_raw TEXT PRIMARY KEY,
    lat          REAL,
    lon          REAL,
    resolved_at  TEXT NOT NULL
);
