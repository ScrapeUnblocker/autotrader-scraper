# autotrader-scraper

[![CI](https://github.com/ScrapeUnblocker/autotrader-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/ScrapeUnblocker/autotrader-scraper/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Scrape Autotrader car listings into clean, typed JSON or CSV — no HTML selectors, no blocks.**

Give it a make/model (or a full Autotrader URL) and get back a tidy list of
vehicles: title, year, make, model, trim, VIN, price, mileage, engine,
transmission, drivetrain, fuel type, exterior/interior color, condition, dealer,
location, listing URL and image.

> **Powered by [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos).**
> Autotrader is rendered in a real browser and returned as AI-parsed structured
> data through the [`getPageSource` parsed-data API](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos),
> so this library never scrapes raw HTML or maintains brittle CSS selectors.

## Features

- 🚗 **Search or browse** — pass a make/model phrase (`"toyota tacoma"`), `"all"`,
  or a full Autotrader search/filter URL, with optional `--zip` and `--radius`.
- 🧱 **Clean, typed output** — a `Vehicle` dataclass with consistent fields;
  export to JSON or CSV in one call.
- 🧩 **Normalized & validated** — the schema.org condition URL is decoded to
  `Used`/`New`, the grouped mileage string becomes an integer with a friendly
  unit, prices are validated and stamped with a currency, the drivetrain is read
  whether Autotrader files it under `drivetrain`, `drive_type` or
  `drive_wheel_configuration` (and the dealer under `dealer` or `dealer_name`),
  and the dealer city/state is lifted out of the description prose.
- 📄 **Clean pagination** — follows Autotrader's `?page=N` links with `--pages`.
- ♻️ **Multi-query + de-dupe** — merge several searches and drop duplicate
  vehicles by listing id / VIN.
- 🔁 **Resilient** — automatic retries with backoff on transient upstream errors.
- 🖥️ **CLI + library** — use `autotrader-scraper` from the shell or import it in Python.

## Install

```bash
pip install .
# or, for development:
pip install -e ".[dev]"
```

Set your ScrapeUnblocker API key (grab one from your
[dashboard](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)):

```bash
cp .env.example .env          # then edit it, or just export the variable:
export SCRAPEUNBLOCKER_KEY=your_key_here
```

## CLI usage

```bash
# Search a make/model near a ZIP and print JSON to stdout
autotrader-scraper "toyota tacoma" --zip 78701 --radius 100

# Merge multiple searches, follow 2 pages each, cap at 60 vehicles
autotrader-scraper "honda civic" "toyota corolla" --pages 2 --limit 60

# Browse everything near a ZIP and export to CSV
autotrader-scraper "all" --zip 90210 --format csv --output cars.csv

# Scrape a full filter URL you built in the browser, pretty-printed
autotrader-scraper "https://www.autotrader.com/cars-for-sale/tesla/model-3" --pretty
```

```
usage: autotrader-scraper [-h] [-z ZIP] [-r MILES] [-c ISO] [-p PAGES]
                          [-n LIMIT] [-f {json,csv}] [-o PATH] [--pretty]
                          [--version]
                          QUERY [QUERY ...]
```

A query is treated as `make model` (`"ford f-150"` →
`/cars-for-sale/ford/f-150`); `"all"` browses every listing. Multi-word makes
(e.g. Mercedes-Benz) are easiest to pass as a full URL. Autotrader is a US
marketplace, so requests default to routing through the US (`--country US`).

## Library usage

```python
from autotrader_scraper import AutotraderScraper, to_csv

scraper = AutotraderScraper()  # reads SCRAPEUNBLOCKER_KEY
cars = scraper.scrape(
    ["toyota tacoma", "ford f-150"],  # make/model phrases and/or full URLs
    zip_code="78701",
    radius=100,
    pages=2,
    limit=60,
)

for c in cars:
    price = f"${c.price:,.0f}" if c.price is not None else "no price"
    miles = f"{c.mileage:,} {c.mileage_unit}" if c.mileage is not None else "mileage n/a"
    print(c.year, c.make, c.model, price, miles)

to_csv(cars, "autotrader.csv")
```

## Example output

```json
[
  {
    "title": "Certified 2020 Honda Accord Sport",
    "year": 2020,
    "make": "Honda",
    "model": "Accord",
    "trim": null,
    "condition": "Used",
    "price": 22250.0,
    "currency": "USD",
    "mileage": 53849,
    "mileage_unit": "mi",
    "vin": "1HGCV1F30LA113758",
    "engine": "30L",
    "transmission": "Continuously Variable Automatic",
    "drivetrain": "2 Wheel Drive - Front",
    "fuel_type": "Gasoline",
    "exterior_color": "Silver",
    "interior_color": "Black",
    "dealer_name": "Airport Marina Honda",
    "location": "Los Angeles, CA",
    "listing_id": "790959375",
    "url": "https://www.autotrader.com/cars-for-sale/vehicle/790959375",
    "image": "https://images.autotrader.com/hn/c/....jpg"
  }
]
```

Optional specs are `null` when Autotrader does not expose them for a row. Prices
are validated and mileage is decoded from Autotrader's grouped string
(`"53,849"` → `53849`), so downstream code can trust the types.

## Project layout

```
src/autotrader_scraper/
  __init__.py      package exports + version
  scraper.py       Vehicle model, AutotraderScraper, normalization, JSON/CSV export
  cli.py           argparse command-line interface
examples/          runnable scripts (search → JSON, CSV export, best value by mileage)
tests/             offline unit tests (SDK mocked — no API credit spent)
```

## Development

```bash
make install       # editable install with dev deps
make lint          # ruff check
make format        # ruff format
make test          # pytest (offline; the SDK is mocked)
make run           # run the search → JSON example (needs SCRAPEUNBLOCKER_KEY)
```

The test suite mocks the ScrapeUnblocker client, so `make test` runs fully
offline and spends no API credits.

## Links

- 🌐 [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
- 📚 [Documentation](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
- 🐍 [Python SDK](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)

## Legal

For research and educational use. Respect Autotrader's Terms of Service and
`robots.txt`, and applicable laws, when scraping. This project is not affiliated
with or endorsed by Autotrader.com, Inc.

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 ScrapeUnblocker.
