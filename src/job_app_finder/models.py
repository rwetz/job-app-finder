from dataclasses import dataclass


@dataclass(frozen=True)
class Anchor:
    name: str
    zip: str
    lat: float
    lon: float


@dataclass
class Posting:
    source: str
    external_id: str
    title: str
    company: str
    location_raw: str | None
    lat: float | None
    lon: float | None
    is_remote: bool
    url: str
    description: str | None
    posted_at: str | None
    fetched_at: str
    location_tier: int | None = None
    match_score: float | None = None
    match_rationale: str | None = None
