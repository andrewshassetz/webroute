"""A tiny Claude agent that searches the web through the router.

Claude gets ONE tool, `web_search`. It doesn't know or care which provider
answers; the router handles that, including fallback.

    export ANTHROPIC_API_KEY=...
    python agent.py "What is the Model Context Protocol and who made it?"
    python agent.py --outage wikipedia "What is LangChain?"
"""

import argparse
import json
import os

import anthropic
from rich.console import Console

from webroute import Router, default_providers

console = Console()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

TOOLS = [{
    "name": "web_search",
    "description": "Search the web. Returns a few results with title, url and snippet.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "What to search for"}},
        "required": ["query"],
    },
}]


def run(question: str, router: Router, max_turns: int = 5) -> str:
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]

    for _ in range(max_turns):
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, tools=TOOLS, messages=messages,
            system="Answer briefly. Use web_search when you need facts. Cite URLs.",
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")

        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            query = block.input["query"]
            console.print(f"[cyan]tool call[/cyan] web_search({query!r})")
            routed = router.search(query)
            for line in routed.trace:
                console.print(f"   [dim]{line}[/dim]")
            payload = [r.__dict__ for r in routed.results] or {"error": "no results"}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(payload),
            })
        messages.append({"role": "user", "content": tool_results})

    return "(stopped: too many tool calls)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--policy", default="cheap", choices=["cheap", "fast", "quality"])
    ap.add_argument("--outage", action="append", default=[])
    args = ap.parse_args()

    providers = default_providers()
    for p in providers:
        p.simulate_outage = p.name in args.outage

    answer = run(args.question, Router(providers, policy=args.policy))
    console.rule("[bold]answer")
    console.print(answer)


if __name__ == "__main__":
    main()
