"""Search Autotrader and print the results as JSON.

Run:
    export SCRAPEUNBLOCKER_KEY=your_key_here   # Windows: set SCRAPEUNBLOCKER_KEY=...
    python examples/search_to_json.py
"""

from __future__ import annotations

from autotrader_scraper import AutotraderScraper, to_json


def main() -> None:
    scraper = AutotraderScraper()  # reads SCRAPEUNBLOCKER_KEY from the environment
    cars = scraper.scrape(["toyota tacoma"], zip_code="78701", radius=100)

    print(f"Found {len(cars)} vehicles\n")
    print(to_json(cars[:5]))


if __name__ == "__main__":
    main()
