"""Terminal demo of the router. No API keys needed.

    python demo.py                         # normal run
    python demo.py --outage wikipedia      # knock a provider out, watch the fallback
    python demo.py --policy quality "latest AI agent news"
"""

import argparse

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from webroute import Router, default_providers

console = Console()

DEFAULT_QUERIES = [
    "what is the Model Context Protocol",
    "history of web search engines",
]


def show(query: str, router: Router) -> None:
    console.rule(f"[bold]{query}")
    result = router.search(query)

    for line in result.trace:
        style = "red" if line.startswith("FAIL") else (
            "green" if line.startswith("OK") else "dim")
        console.print(f"  [{style}]{line}[/{style}]")

    if not result.results:
        console.print("[red]  no results[/red]")
        return

    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("via", width=11)
    table.add_column("title", width=32)
    table.add_column("snippet")
    for r in result.results:
        table.add_row(r.provider, r.title, r.snippet[:110])
    console.print(table)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queries", nargs="*", default=DEFAULT_QUERIES)
    ap.add_argument("--policy", default="cheap", choices=["cheap", "fast", "quality"])
    ap.add_argument("--outage", action="append", default=[],
                    help="provider name to simulate as down (repeatable)")
    args = ap.parse_args()

    providers = default_providers()
    for p in providers:
        p.simulate_outage = p.name in args.outage

    console.print(Panel.fit(
        f"[bold]webroute[/bold] demo  |  policy: {args.policy}  |  "
        f"down: {', '.join(args.outage) or 'none'}"))

    router = Router(providers, policy=args.policy)
    for q in args.queries:
        show(q, router)


if __name__ == "__main__":
    main()
