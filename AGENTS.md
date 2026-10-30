# Job Application Finder

Local-first job and internship aggregator: ingest postings, dedupe, rank local first (Fargo, ND and Rochester, MN), then remote, then far, scored against a resume. Streamlit UI.

Workspace rules live in `Dev/AGENTS.md`. This file holds only what is specific to this project.

## Design family

Neither Ferrite nor Nexis (Python app). RAW Titanium if styling is needed.

## Run and test

| Task | Command |
|---|---|
| Test | `pytest` (dev extra in `pyproject.toml`) |
| Run the UI | see `README.md` (Streamlit; config in `.streamlit/`, `config.yaml`, `companies.yaml`) |

## Layout

| Path | What lives there |
|---|---|
| `src/job_app_finder/` | Package. `jev_fit.py` is the Jev contract the whole workspace points at |
| `tests/` | pytest suite |
| `docs/SPEC.md` | Full spec and the Location and Ranking Model. Read before changing ranking |
| `scripts/` | Includes `jev_shadow.py`, which records the Jev receipt |
| `data/` | Local data and caches |

## Do not touch

- `.env` holds API keys (Adzuna, JSearch, USAJobs). Never print, log or commit it.
- Never apply to a job on the user's behalf. Applying is irreversible and stays behind human confirmation.
- Do not edit `jev_fit.py` casually: `Dev/AGENTS.md` cites it as the reference contract. Jev only ranks, routes or flags.

## Why it is built this way

- Location tiering (0 to 3) runs before everything else because the user wants in-person local roles first.
- Dedup uses canonical URLs plus a fuzzy key and merges sources, so one posting seen on three boards shows once.
