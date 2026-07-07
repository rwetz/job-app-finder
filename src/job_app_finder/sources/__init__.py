from job_app_finder.sources.base import AdapterMeta, SourceAdapter, get_registry, register

# Import built-in adapters for their registration side effect.
from job_app_finder.sources import (  # noqa: E402,F401
    adzuna,
    greenhouse,
    handshake,
    jsearch,
    lever,
    remoteok,
    remotive,
    usajobs,
    workday,
)

__all__ = ["AdapterMeta", "SourceAdapter", "get_registry", "register"]
