"""Command-line interface for autotrader-scraper.

Examples:
    autotrader-scraper "toyota tacoma" --zip 78701 --radius 100
    autotrader-scraper "honda civic" "toyota corolla" --pages 2 --limit 60
    autotrader-scraper "all" --zip 90210 --format csv --output cars.csv
    autotrader-scraper "https://www.autotrader.com/cars-for-sale/tesla/model-3" --pretty
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__
from .scraper import AutotraderScraper, to_csv, to_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autotrader-scraper",
        description="Scrape Autotrader car listings into clean JSON or CSV "
        "via the ScrapeUnblocker parsed-data API.",
    )
    parser.add_argument(
        "queries",
        nargs="+",
        metavar="QUERY",
        help='Make/model phrase(s) ("toyota tacoma"), "all", or full Autotrader '
        "URL(s). Multiple values are merged and deduplicated.",
    )
    parser.add_argument(
        "-z",
        "--zip",
        dest="zip_code",
        metavar="ZIP",
        help="ZIP code to centre the search on (ignored for full-URL queries).",
    )
    parser.add_argument(
        "-r",
        "--radius",
        type=int,
        default=None,
        metavar="MILES",
        help="Search radius in miles (ignored for full-URL queries).",
    )
    parser.add_argument(
        "-c",
        "--country",
        default="US",
        metavar="ISO",
        help="Proxy country to route through (default: US — Autotrader is US-only).",
    )
    parser.add_argument(
        "-p",
        "--pages",
        type=int,
        default=1,
        help="Max pages to follow per query (default: 1).",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=None,
        help="Stop after this many unique vehicles.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help="Write to this file instead of stdout.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON (indented).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _write_output(text: str, output: str | None) -> None:
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        # Listing titles/colors can carry non-ASCII glyphs; force UTF-8 so
        # piping on a legacy Windows console does not raise.
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
        print(text)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    scraper = AutotraderScraper()
    vehicles = scraper.scrape(
        args.queries,
        proxy_country=args.country,
        zip_code=args.zip_code,
        radius=args.radius,
        pages=args.pages,
        limit=args.limit,
    )

    if args.format == "csv":
        if not args.output:
            print("error: --format csv requires --output PATH", file=sys.stderr)
            return 2
        to_csv(vehicles, args.output)
        print(f"Wrote {len(vehicles)} vehicles to {args.output}", file=sys.stderr)
        return 0

    text = to_json(vehicles, indent=2 if args.pretty else None)
    _write_output(text, args.output)
    if args.output:
        print(f"Wrote {len(vehicles)} vehicles to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
