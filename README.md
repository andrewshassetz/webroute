# webroute

One search tool for AI agents, many providers behind it.

`webroute` gives an agent a single `web_search` tool. Underneath, a small router works out what kind of query it is, picks the best provider for it, and falls back to the next one if a provider is down, returns nothing, or has no API key set. It also logs the reason for each decision, so you never have to guess which provider answered or why.

```
task=reference policy=cheap
skip tavily: no TAVILY_API_KEY set
order: wikipedia -> duckduckgo
FAIL wikipedia: simulated outage (HTTP 503) -> falling back
OK duckduckgo: 3 results in 412 ms
```

## Why

Most agent setups hard-wire one search API. When that API rate-limits you, goes down, or just isn't the right fit for the question, the agent fails with it. Here the agent only knows about one tool, and the router takes care of everything after that.

## What's inside

| File | What it does |
|---|---|
| `webroute/providers.py` | Wikipedia, DuckDuckGo (both free, no key) and Tavily (optional key), all with the same interface |
| `webroute/router.py` | Sorts each query into a task type, ranks providers by policy, falls back, and uses a simple circuit breaker |
| `demo.py` | Terminal demo of the routing that needs no API keys |
| `agent.py` | A Claude agent with tool calling that uses the router as its `web_search` tool |
| `tests/` | Offline tests with fake providers |

## Run it

```bash
pip install -r requirements.txt

# 1. Routing demo (no keys needed)
python demo.py

# 2. Knock a provider out and watch it fall back
python demo.py --outage wikipedia "what is LangChain"

# 3. Change the policy
python demo.py --policy quality "latest AI agent news"

# 4. A real agent with tool calling
export ANTHROPIC_API_KEY=sk-ant-...
python agent.py "What is the Model Context Protocol and who created it?"
python agent.py --outage wikipedia "What is LangChain?"

# Tests
pytest -q
```

To bring a paid provider into the rotation, set `TAVILY_API_KEY`.

## How routing works

1. **Classify.** Keyword hints sort each query into `reference`, `news`, `research` or `general`.
2. **Filter.** Providers that have no key set, or that have failed too many times in a row (the circuit breaker), are skipped.
3. **Rank.** Providers that list the task as a capability go first. After that, the policy decides the order:
   - `cheap` puts free providers first
   - `fast` puts the lowest latency first
   - `quality` puts the best results first
4. **Try in order.** The first provider that returns results wins. An error or an empty result moves on to the next provider.

## Add a provider

```python
from webroute import Provider, SearchResult

class MyProvider(Provider):
    def __init__(self, **kw):
        super().__init__(name="mine", capabilities={"news"},
                         cost_per_call=0.002, avg_latency_ms=300, quality=4, **kw)

    def _search(self, query, max_results):
        ...
        return [SearchResult(title, url, snippet, self.name)]
```

## Limits

This is a small demo, not a production library. Task classification uses keywords, and the cost and latency numbers are hand-set estimates rather than measured values.

## License

MIT
