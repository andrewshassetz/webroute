"""The router: pick the best provider for a task, fall back if it fails.

It explains every decision in a `trace`, so you can see *why* it chose
a provider, not just which one it chose.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .providers import Provider, ProviderError, SearchResult

# How each policy weighs a provider. Higher score wins.
POLICIES = {
    "cheap":   lambda p: -p.cost_per_call * 1000 + p.quality * 0.1,
    "fast":    lambda p: -p.avg_latency_ms / 100 + p.quality * 0.1,
    "quality": lambda p: p.quality * 10 - p.cost_per_call * 100,
}

# Simple keyword hints to guess what kind of task a query is.
TASK_HINTS = {
    "news": ["latest", "today", "this week", "news", "announced", "2025", "2026"],
    "research": ["compare", "vs", "pros and cons", "deep dive", "analysis"],
    "reference": ["what is", "who is", "define", "history of", "meaning of"],
}


def classify(query: str) -> str:
    q = query.lower()
    for task, words in TASK_HINTS.items():
        if any(w in q for w in words):
            return task
    return "general"


@dataclass
class RouteResult:
    results: list[SearchResult]
    provider: str | None
    task: str
    trace: list[str] = field(default_factory=list)


class Router:
    def __init__(self, providers: list[Provider], policy: str = "cheap",
                 max_failures: int = 2):
        if policy not in POLICIES:
            raise ValueError(f"policy must be one of {list(POLICIES)}")
        self.providers = providers
        self.policy = policy
        self.max_failures = max_failures
        self.failures: dict[str, int] = {}

    def plan(self, task: str) -> tuple[list[Provider], list[str]]:
        """Return providers in the order we'll try them, plus the reasons."""
        notes = []
        candidates = []
        for p in self.providers:
            if not p.available():
                notes.append(f"skip {p.name}: no {p.needs_key} set")
            elif self.failures.get(p.name, 0) >= self.max_failures:
                notes.append(f"skip {p.name}: circuit open after "
                             f"{self.failures[p.name]} failures")
            else:
                candidates.append(p)

        score = POLICIES[self.policy]
        # Providers that list this task as a capability go first.
        ranked = sorted(candidates,
                        key=lambda p: (task in p.capabilities, score(p)),
                        reverse=True)
        return ranked, notes

    def search(self, query: str, max_results: int = 3) -> RouteResult:
        task = classify(query)
        order, trace = self.plan(task)
        trace.insert(0, f"task={task} policy={self.policy}")
        trace.append("order: " + " -> ".join(p.name for p in order) if order
                     else "order: (no providers available)")

        for p in order:
            start = time.perf_counter()
            try:
                results = p.search(query, max_results)
            except ProviderError as exc:
                self.failures[p.name] = self.failures.get(p.name, 0) + 1
                trace.append(f"FAIL {exc} -> falling back")
                continue
            ms = int((time.perf_counter() - start) * 1000)
            if not results:
                trace.append(f"EMPTY {p.name} returned 0 results ({ms} ms) -> falling back")
                continue
            self.failures[p.name] = 0
            trace.append(f"OK {p.name}: {len(results)} results in {ms} ms")
            return RouteResult(results, p.name, task, trace)

        trace.append("all providers failed")
        return RouteResult([], None, task, trace)
