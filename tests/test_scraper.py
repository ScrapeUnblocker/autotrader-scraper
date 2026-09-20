"""Offline tests for AutotraderScraper: de-dupe, pagination, retry — fake client."""

from __future__ import annotations

import pytest

from autotrader_scraper import AutotraderScraper, Vehicle


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeClient:
    """Records calls and returns queued responses (or raises queued errors)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def get_parsed(self, url, proxy_country=None):
        self.calls.append((url, proxy_country))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResult(item)


def _item(listing_id, title="Autotrader Vehicle"):
    return {
        "title": title,
        "price": {"value": 19999, "currency": None},
        "url": f"https://www.autotrader.com/cars-for-sale/vehicle/{listing_id}",
        "listing_id": listing_id,
    }


class Transient(Exception):
    """Stand-in for a retryable SDK error (simple ctor, offline-safe)."""


def test_scrape_returns_vehicles_and_builds_url_with_params():
    client = FakeClient([{"items": [_item(1), _item(2)]}])
    scraper = AutotraderScraper(client=client)
    vehicles = scraper.scrape(["toyota tacoma"], zip_code="78701", radius=100)

    assert len(vehicles) == 2
    assert all(isinstance(v, Vehicle) for v in vehicles)
    assert client.calls[0][0] == (
        "https://www.autotrader.com/cars-for-sale/toyota/tacoma?zip=78701&searchRadius=100"
    )
    assert client.calls[0][1] == "US"


def test_default_country_is_us():
    client = FakeClient([{"items": [_item(1)]}])
    AutotraderScraper(client=client).scrape(["honda civic"])
    assert client.calls[0][1] == "US"


def test_scrape_dedupes_across_queries_by_listing_id():
    dupe = _item(1)
    client = FakeClient([{"items": [dupe]}, {"items": [dupe, _item(3)]}])
    scraper = AutotraderScraper(client=client)
    vehicles = scraper.scrape(["honda civic", "honda accord"])
    assert len(vehicles) == 2  # the shared listing id is collapsed


def test_limit_stops_collection_early():
    items = [_item(1), _item(2), _item(3)]
    client = FakeClient([{"items": items}])
    scraper = AutotraderScraper(client=client)
    vehicles = scraper.scrape(["all"], limit=2)
    assert len(vehicles) == 2


def test_pagination_follows_next_page():
    client = FakeClient(
        [
            {
                "items": [_item(1)],
                "next_page": "https://www.autotrader.com/cars-for-sale/all-cars?page=2",
            },
            {"items": [_item(2)], "next_page": None},
        ]
    )
    scraper = AutotraderScraper(client=client)
    vehicles = scraper.scrape(["all"], pages=3)
    assert len(vehicles) == 2
    assert client.calls[1][0].endswith("page=2")


def test_retries_transient_then_succeeds():
    sleeps: list[float] = []
    client = FakeClient([Transient(), Transient(), {"items": [_item(1)]}])
    scraper = AutotraderScraper(
        client=client,
        retries=2,
        backoff=0.5,
        transient_errors=(Transient,),
        sleep=sleeps.append,
    )
    vehicles = scraper.scrape(["all"])
    assert len(vehicles) == 1
    assert sleeps == [0.5, 1.0]  # linear backoff


def test_retries_exhausted_reraises():
    client = FakeClient([Transient(), Transient(), Transient()])
    scraper = AutotraderScraper(
        client=client, retries=1, transient_errors=(Transient,), sleep=lambda _s: None
    )
    with pytest.raises(Transient):
        scraper.scrape(["all"])


def test_non_transient_error_is_not_retried():
    client = FakeClient([ValueError("boom")])
    scraper = AutotraderScraper(client=client, transient_errors=(Transient,), sleep=lambda _s: None)
    with pytest.raises(ValueError):
        scraper.scrape(["all"])
    assert len(client.calls) == 1
