from abc import ABC, abstractmethod
from dataclasses import dataclass

from job_app_finder.models import Anchor, Posting


@dataclass(frozen=True)
class AdapterMeta:
    name: str
    kind: str  # aggregator | ats | board | besteffort
    priority: int
    requires_auth: bool = False
    tos_risk: str = "none"  # none | low | medium | high


class SourceAdapter(ABC):
    meta: AdapterMeta

    @abstractmethod
    async def fetch(self, queries: list[str], anchors: list[Anchor]) -> list[Posting]:
        """Fetch and normalize postings from this source."""


_REGISTRY: dict[str, SourceAdapter] = {}


def register(adapter: SourceAdapter) -> SourceAdapter:
    _REGISTRY[adapter.meta.name] = adapter
    return adapter


def get_registry() -> dict[str, SourceAdapter]:
    return dict(_REGISTRY)
