import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

from job_app_finder.models import Anchor

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Config:
    anchors: list[Anchor]
    location_tiers: dict
    seed_queries: list[str]
    enabled_sources: list[str]
    besteffort_enabled: list[str]
    refresh_interval_minutes: int
    db_path: Path
    link_check_enabled: bool = False
    link_check_interval_hours: int = 6
    companies: dict = field(default_factory=dict)
    resume_path: Path = PROJECT_ROOT / "resume.md"
    claude_model: str = "claude-opus-4-8"
    shortlist_size: int = 10


def load_config(
    config_path: Path = PROJECT_ROOT / "config.yaml",
    companies_path: Path = PROJECT_ROOT / "companies.yaml",
    env_path: Path = PROJECT_ROOT / ".env",
) -> Config:
    load_dotenv(env_path)

    raw = yaml.safe_load(config_path.read_text())
    companies = yaml.safe_load(companies_path.read_text()) if companies_path.exists() else {}

    anchors = [Anchor(**a) for a in raw["anchors"]]

    return Config(
        anchors=anchors,
        location_tiers=raw["location_tiers"],
        seed_queries=raw["seed_queries"],
        enabled_sources=raw["sources"]["enabled"],
        besteffort_enabled=raw["sources"].get("besteffort_enabled", []),
        refresh_interval_minutes=raw["refresh"]["background_interval_minutes"],
        link_check_enabled=raw["refresh"].get("link_check_enabled", False),
        link_check_interval_hours=raw["refresh"].get("link_check_interval_hours", 6),
        db_path=PROJECT_ROOT / raw["database"]["path"],
        companies=companies,
        resume_path=PROJECT_ROOT / raw.get("match", {}).get("resume_path", "resume.md"),
        claude_model=raw.get("match", {}).get("claude_model", "claude-opus-4-8"),
        shortlist_size=raw.get("match", {}).get("shortlist_size", 10),
    )


def get_env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def load_companies(companies_path: Path = PROJECT_ROOT / "companies.yaml") -> dict:
    """Standalone companies.yaml reader for ATS adapters (no anchors/queries needed)."""
    if not companies_path.exists():
        return {}
    return yaml.safe_load(companies_path.read_text()) or {}
