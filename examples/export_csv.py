"""Collect several Autotrader searches and export a de-duplicated CSV.

Run:
    export SCRAPEUNBLOCKER_KEY=your_key_here   # Windows: set SCRAPEUNBLOCKER_KEY=...
    python examples/export_csv.py
"""

from __future__ import annotations

from autotrader_scraper import AutotraderScraper, to_csv

QUERIES = ["honda civic", "toyota corolla", "mazda mazda3"]
OUTPUT = "autotrader_compacts.csv"


def main() -> None:
    scraper = AutotraderScraper()
    cars = scraper.scrape(QUERIES, zip_code="60601", radius=100, pages=2)
    to_csv(cars, OUTPUT)
    print(f"Wrote {len(cars)} unique vehicles across {len(QUERIES)} searches to {OUTPUT}")


if __name__ == "__main__":
    main()
