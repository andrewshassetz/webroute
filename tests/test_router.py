"""Offline tests: fake providers, no network."""

from webroute import Provider, ProviderError, Router, SearchResult, classify


class Fake(Provider):
    def __init__(self, name, fail=False, empty=False, **kw):
        super().__init__(name=name, **kw)
        self.fail, self.empty, self.calls = fail, empty, 0

    def _search(self, query, max_results):
        self.calls += 1
        if self.fail:
            raise ProviderError(f"{self.name}: boom")
        if self.empty:
            return []
        return [SearchResult("t", "u", "s", self.name)]


def test_classify():
    assert classify("what is MCP") == "reference"
    assert classify("latest agent news") == "news"
    assert classify("LangChain vs LlamaIndex") == "research"
    assert classify("pizza dough") == "general"


def test_cheap_policy_prefers_free():
    paid = Fake("paid", capabilities={"general"}, cost_per_call=0.01, quality=5)
    free = Fake("free", capabilities={"general"}, cost_per_call=0.0, quality=3)
    r = Router([paid, free], policy="cheap").search("pizza dough")
    assert r.provider == "free"


def test_quality_policy_prefers_best():
    paid = Fake("paid", capabilities={"general"}, cost_per_call=0.01, quality=5)
    free = Fake("free", capabilities={"general"}, cost_per_call=0.0, quality=2)
    r = Router([paid, free], policy="quality").search("pizza dough")
    assert r.provider == "paid"


def test_capability_match_wins():
    news = Fake("news", capabilities={"news"}, cost_per_call=0.01)
    ref = Fake("ref", capabilities={"reference"})
    assert Router([ref, news]).search("latest agent news").provider == "news"


def test_fallback_on_failure_and_empty():
    a = Fake("a", fail=True, capabilities={"general"})
    b = Fake("b", empty=True, capabilities={"general"})
    c = Fake("c", capabilities={"general"}, quality=1)
    r = Router([a, b, c]).search("pizza")
    assert r.provider == "c"
    assert any(line.startswith("FAIL") for line in r.trace)


def test_circuit_breaker_skips_dead_provider():
    a = Fake("a", fail=True, capabilities={"general"}, quality=5)
    b = Fake("b", capabilities={"general"}, quality=1)
    router = Router([a, b], max_failures=2)
    for _ in range(3):
        router.search("pizza")
    assert a.calls == 2  # third time it was skipped


def test_missing_key_is_skipped(monkeypatch):
    monkeypatch.delenv("FAKE_KEY", raising=False)
    keyed = Fake("keyed", needs_key="FAKE_KEY", capabilities={"general"}, quality=5)
    free = Fake("free", capabilities={"general"})
    assert Router([keyed, free]).search("pizza").provider == "free"
