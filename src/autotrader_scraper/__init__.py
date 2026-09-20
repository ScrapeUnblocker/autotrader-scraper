"""autotrader-scraper — clean Autotrader car listings via the ScrapeUnblocker API.

Scrape Autotrader search results into clean, typed JSON: title, year, make,
model, trim, VIN, price, mileage, engine, transmission, drivetrain, fuel type,
exterior/interior color, condition, dealer, location, listing URL and image.
Powered by the ScrapeUnblocker ``getPageSource`` parsed-data API, which renders
the page in a real browser and returns AI-parsed structured data — so you never
touch HTML selectors.

Example:
    >>> from autotrader_scraper import AutotraderScraper
    >>> scraper = AutotraderScraper()                       # reads SCRAPEUNBLOCKER_KEY
    >>> cars = scraper.scrape(["toyota tacoma"], zip_code="78701")  # doctest: +SKIP
    >>> cars[0].make, cars[0].model                         # doctest: +SKIP
    ('Toyota', 'Tacoma')
"""

from __future__ import annotations

from .scraper import (
    AutotraderScraper,
    Vehicle,
    build_search_url,
    normalize_item,
    to_csv,
    to_json,
    vehicles_to_dicts,
)

__all__ = [
    "AutotraderScraper",
    "Vehicle",
    "build_search_url",
    "normalize_item",
    "vehicles_to_dicts",
    "to_csv",
    "to_json",
]

__version__ = "0.1.0"
