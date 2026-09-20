"""Rank an Autotrader search by lowest price, then lowest mileage.

Collects a couple of pages, keeps listings that have both a price and a mileage
reading, and prints the best-value cars first — a quick demo of the clean core
fields (price, mileage, year, make, model, dealer, location).

Run:
    export SCRAPEUNBLOCKER_KEY=your_key_here   # Windows: set SCRAPEUNBLOCKER_KEY=...
    python examples/cheapest_by_mileage.py
"""

from __future__ import annotations

from autotrader_scraper import AutotraderScraper


def main() -> None:
    scraper = AutotraderScraper()
    cars = scraper.scrape(["ford f-150"], zip_code="75201", radius=100, pages=2)

    priced = sorted(
        (c for c in cars if c.price is not None and c.mileage is not None),
        key=lambda c: (c.price, c.mileage),
    )
    print(f"{len(cars)} vehicles, {len(priced)} with price + mileage — best value first\n")
    for c in priced[:10]:
        year = f"{c.year} " if c.year else ""
        loc = f"  [{c.location}]" if c.location else ""
        print(f"${c.price:,.0f}  {c.mileage:,} {c.mileage_unit or 'mi'}  {year}{c.title}{loc}")


if __name__ == "__main__":
    main()
