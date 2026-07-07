from job_app_finder.sources.base import AdapterMeta, SourceAdapter, get_registry, register


class _FakeAdapter(SourceAdapter):
    meta = AdapterMeta(name="fake", kind="aggregator", priority=1)

    async def fetch(self, queries, anchors):
        return []


def test_register_adds_adapter_to_registry():
    register(_FakeAdapter())
    assert "fake" in get_registry()
