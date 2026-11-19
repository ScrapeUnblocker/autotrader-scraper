"""Core scraping logic for autotrader-scraper.

The heavy lifting is done by the ScrapeUnblocker ``get_parsed`` endpoint, which
loads an Autotrader page in a real browser and returns AI-parsed structured
data. This module normalizes that data into a clean, stable :class:`Vehicle`
shape, handles multi-page collection with de-duplication, retries transient
upstream errors, and exports to JSON/CSV.

Autotrader listings carry a rich, mostly stable field set — title, year, make,
model, trim, VIN, price, mileage, engine, transmission, drivetrain, fuel type,
exterior/interior color, condition, dealer and listing URL/image. A few fields
need normalizing before they are useful:

* ``price`` arrives as ``{"value": 22250, "currency": null}`` — the parser
  leaves that currency null on the US storefront, so we read the per-item
  ``currency`` field when present and otherwise stamp ``USD``.
* ``mileage`` is a grouped string (``"53,849"``) with a separate
  ``mileage_unit`` (``"SMI"`` statute miles / ``"KMT"`` kilometres); we parse it
  to an integer and normalize the unit to ``"mi"``/``"km"``.
* ``condition`` is a schema.org URL (``"http://schema.org/UsedCondition"``); we
  map it to a plain ``"Used"``/``"New"``.
* the drivetrain lands under ``drivetrain``, ``drive_type`` or
  ``drive_wheel_configuration`` depending on the row — we read any of them.
* the dealer comes back as ``dealer`` or ``dealer_name`` — we read either.
* ``fuel_efficiency`` just echoes ``fuel_type`` on most rows, so we drop it.
* the dealer city/state is only spelled out in the ``description`` prose
  (``"Location: Los Angeles, CA. ..."``); we lift it into a ``location`` field.
"""

from __future__ import annotations

import csv
import json
import re
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import quote

AUTOTRADER_SEARCH_URL = "https://www.autotrader.com/cars-for-sale/{path}"

# Autotrader's US storefront quotes prices in USD, but the parser leaves the
# per-item currency null, so we stamp it ourselves.
DEFAULT_CURRENCY = "USD"

# Odometer unit codes Autotrader emits, mapped to friendly abbreviations.
_MILEAGE_UNITS = {"SMI": "mi", "KMT": "km"}


def _transient_errors() -> tuple[type[BaseException], ...]:
    """Best-effort tuple of ScrapeUnblocker exceptions worth retrying.

    Imported lazily so the package is usable (and unit-testable) even when the
    ``scrapeunblocker`` SDK is not installed.
    """
    try:
        from scrapeunblocker import (  # type: ignore
            BrowserTimeoutError,
            RateLimitError,
            ScrapeTimeoutError,
            ServerError,
            UpstreamOutageError,
        )
        from scrapeunblocker import (
            ConnectionError as SUConnectionError,
        )
    except Exception:  # pragma: no cover - depends on SDK availability
        return ()
    return (
        UpstreamOutageError,
        RateLimitError,
        ScrapeTimeoutError,
        BrowserTimeoutError,
        ServerError,
        SUConnectionError,
    )


@dataclass
class Vehicle:
    """A single Autotrader car listing.

    ``title``, ``price``, ``currency``, ``url`` and ``image`` are populated for
    essentially every listing. The remaining specs (``year`` ... ``dealer_name``)
    are populated when Autotrader exposes them for that row, and are ``None``
    otherwise.
    """

    title: str | None = None
    year: int | None = None
    make: str | None = None
    model: str | None = None
    trim: str | None = None
    condition: str | None = None
    price: float | None = None
    currency: str | None = None
    mileage: int | None = None
    mileage_unit: str | None = None
    vin: str | None = None
    engine: str | None = None
    transmission: str | None = None
    drivetrain: str | None = None
    fuel_type: str | None = None
    exterior_color: str | None = None
    interior_color: str | None = None
    dealer_name: str | None = None
    location: str | None = None
    listing_id: str | None = None
    url: str | None = None
    image: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Column order used for CSV export and dict serialization.
FIELDNAMES: tuple[str, ...] = (
    "title",
    "year",
    "make",
    "model",
    "trim",
    "condition",
    "price",
    "currency",
    "mileage",
    "mileage_unit",
    "vin",
    "engine",
    "transmission",
    "drivetrain",
    "fuel_type",
    "exterior_color",
    "interior_color",
    "dealer_name",
    "location",
    "listing_id",
    "url",
    "image",
)


def _slug(text: str) -> str:
    """Lowercase, strip and hyphenate a token for an Autotrader path segment."""
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


def build_search_url(
    query: str,
    *,
    zip_code: str | None = None,
    radius: int | None = None,
) -> str:
    """Return an Autotrader search URL for ``query``.

    A value that already looks like an ``http(s)`` URL is returned unchanged
    (with ``zip``/``radius`` ignored), so callers can paste a hand-tuned search
    or filtered URL straight from the browser.

    Otherwise ``query`` is treated as a make/model phrase: the first word is the
    make and the rest is the model, e.g. ``"toyota tacoma"`` ->
    ``/cars-for-sale/toyota/tacoma`` and ``"ford f-150"`` ->
    ``/cars-for-sale/ford/f-150``. An empty query or ``"all"`` / ``"all cars"``
    maps to ``/cars-for-sale/all-cars``. Multi-word makes (e.g. "mercedes benz")
    are best passed as a full URL. ``zip_code`` and ``radius`` add location
    filtering when provided.
    """
    q = query.strip()
    if q.lower().startswith(("http://", "https://")):
        return q

    tokens = q.split()
    if not tokens or q.lower() in {"all", "all cars", "all-cars"}:
        path = "all-cars"
    else:
        make = _slug(tokens[0])
        model = _slug("-".join(tokens[1:]))
        path = f"{make}/{model}" if model else make

    url = AUTOTRADER_SEARCH_URL.format(path=path)

    params = []
    if zip_code:
        params.append(f"zip={quote(str(zip_code).strip())}")
    if radius is not None:
        params.append(f"searchRadius={int(radius)}")
    if params:
        url = f"{url}?{'&'.join(params)}"
    return url


def _price_number(obj: Any) -> float | None:
    """Coerce an Autotrader price value into a float, or ``None``.

    Accepts a ``{"value": .., "currency": ..}`` dict, a plain number, or a
    currency string with thousands grouping (``"$22,250"``).
    """
    if isinstance(obj, dict):
        obj = obj.get("value")
    if obj is None or isinstance(obj, bool):
        return None
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, str):
        cleaned = obj.replace(",", "").replace("$", "").strip()
        if re.fullmatch(r"\d+(\.\d+)?", cleaned):
            return float(cleaned)
    return None


def _currency_of(obj: Any) -> str | None:
    if isinstance(obj, dict):
        return obj.get("currency") or None
    return None


def _int(value: Any) -> int | None:
    """Parse a grouped integer string (``"53,849"``) or number into an int."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if re.fullmatch(r"\d+", cleaned):
            return int(cleaned)
    return None


def _year(value: Any) -> int | None:
    """Keep a value only if it is a plausible 4-digit model year."""
    n = _int(value)
    return n if n is not None and 1900 <= n <= 2100 else None


def _condition(value: Any) -> str | None:
    """Map a schema.org condition (or free text) to ``"Used"``/``"New"``.

    ``"http://schema.org/UsedCondition"`` -> ``"Used"``,
    ``"http://schema.org/NewCondition"`` -> ``"New"``. Anything else that
    already mentions "new"/"used"/"certified" is title-cased; otherwise the raw
    value is returned unchanged.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    low = value.lower()
    if "usedcondition" in low or re.search(r"\bused\b", low):
        return "Used"
    if "newcondition" in low or re.search(r"\bnew\b", low):
        return "New"
    if "certified" in low:
        return "Certified"
    return value.strip()


def _mileage_unit(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return _MILEAGE_UNITS.get(value.strip().upper(), value.strip().lower())


_LOCATION_RE = re.compile(r"Location:\s*([^.]+?)\s*\.", re.IGNORECASE)


def _location(description: Any) -> str | None:
    """Lift the dealer city/state out of the ``description`` prose.

    Autotrader descriptions start with ``"Location: Los Angeles, CA. ..."``; we
    return ``"Los Angeles, CA"`` from that, or ``None`` if it is absent.
    """
    if not isinstance(description, str):
        return None
    m = _LOCATION_RE.search(description)
    return m.group(1).strip() if m else None


def _listing_id(raw: dict[str, Any]) -> str | None:
    """Return Autotrader's listing id from the row or the ``/vehicle/<id>`` URL."""
    lid = raw.get("listing_id")
    if lid not in (None, ""):
        return str(lid)
    url = raw.get("url") or ""
    m = re.search(r"/vehicle/(\d+)", url)
    return m.group(1) if m else None


def normalize_item(raw: dict[str, Any]) -> Vehicle:
    """Normalize one parsed Autotrader listing into a :class:`Vehicle`.

    Reads defensively: prices are validated, the schema.org condition and the
    grouped mileage string are decoded, the drivetrain is read from whichever of
    ``drivetrain`` / ``drive_type`` / ``drive_wheel_configuration`` is present,
    the dealer from ``dealer_name`` or ``dealer``, and the dealer location is
    lifted out of the description. The redundant ``fuel_efficiency`` echo of
    ``fuel_type`` is ignored.
    """
    price = _price_number(raw.get("price"))
    currency = (
        _currency_of(raw.get("price"))
        or raw.get("currency")
        or raw.get("price_currency")
        or DEFAULT_CURRENCY
    )

    drivetrain = (
        raw.get("drivetrain")
        or raw.get("drive_type")
        or raw.get("drive_wheel_configuration")
        or None
    )

    mileage = _int(raw.get("mileage"))
    mileage_unit = _mileage_unit(raw.get("mileage_unit"))
    # Autotrader's US storefront always reports the odometer in miles; the
    # parser sometimes omits the unit code, so default it when a reading exists.
    if mileage is not None and mileage_unit is None:
        mileage_unit = "mi"

    return Vehicle(
        title=raw.get("title") or None,
        year=_year(raw.get("year")),
        make=raw.get("make") or None,
        model=raw.get("model") or None,
        trim=raw.get("trim") or None,
        condition=_condition(raw.get("condition")),
        price=price,
        currency=currency if price is not None else None,
        mileage=mileage,
        mileage_unit=mileage_unit,
        vin=raw.get("vin") or None,
        engine=raw.get("engine") or None,
        transmission=raw.get("transmission") or None,
        drivetrain=drivetrain,
        fuel_type=raw.get("fuel_type") or None,
        exterior_color=raw.get("exterior_color") or None,
        interior_color=raw.get("interior_color") or None,
        dealer_name=raw.get("dealer_name") or raw.get("dealer") or None,
        location=_location(raw.get("description")),
        listing_id=_listing_id(raw),
        url=raw.get("url") or None,
        image=raw.get("image") or None,
    )


class AutotraderScraper:
    """Scrape Autotrader car listings via ScrapeUnblocker.

    Args:
        api_key: ScrapeUnblocker key. If omitted, the SDK reads
            ``SCRAPEUNBLOCKER_KEY`` from the environment.
        client: A pre-built client (or any object exposing
            ``get_parsed(url, proxy_country=...)``). Mainly for testing.
        retries: Extra attempts on transient upstream errors.
        backoff: Base seconds for linear backoff between retries.
        timeout: Per-request timeout passed to the SDK client.
        transient_errors: Exception classes treated as retryable. Defaults to
            the ScrapeUnblocker transient set.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any | None = None,
        retries: int = 2,
        backoff: float = 1.0,
        timeout: float = 180.0,
        transient_errors: Sequence[type[BaseException]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if client is None:
            from scrapeunblocker import Client  # local import: optional dep

            client = Client(api_key=api_key, timeout=timeout)
        self._client = client
        self.retries = max(0, int(retries))
        self.backoff = float(backoff)
        self._transient = (
            tuple(transient_errors) if transient_errors is not None else _transient_errors()
        )
        self._sleep = sleep

    def _fetch(self, url: str, proxy_country: str | None) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                result = self._client.get_parsed(url, proxy_country=proxy_country)
                data = getattr(result, "data", None)
                return data if isinstance(data, dict) else {}
            except self._transient:
                if attempt >= self.retries:
                    raise
                attempt += 1
                self._sleep(self.backoff * attempt)

    def scrape(
        self,
        queries: Iterable[str],
        *,
        proxy_country: str | None = "US",
        zip_code: str | None = None,
        radius: int | None = None,
        pages: int = 1,
        limit: int | None = None,
    ) -> list[Vehicle]:
        """Scrape one or more searches and return de-duplicated vehicles.

        Args:
            queries: Make/model phrases (``"toyota tacoma"``), ``"all"``, and/or
                full Autotrader URLs.
            proxy_country: ISO-3166 country to route through. Autotrader is a US
                marketplace, so this defaults to ``"US"``.
            zip_code: Optional ZIP to centre the search on (ignored for queries
                that are already full URLs).
            radius: Optional search radius in miles (ignored for full URLs).
            pages: Max pages to follow per query via the parser's ``next_page``
                link (Autotrader paginates cleanly with ``?page=N``).
            limit: Stop once this many unique vehicles are collected.

        Returns:
            A list of :class:`Vehicle`, de-duplicated by listing id / VIN / URL.
        """
        seen: set[Any] = set()
        vehicles: list[Vehicle] = []

        for query in queries:
            url: str | None = build_search_url(query, zip_code=zip_code, radius=radius)
            page = 0
            while url and page < max(1, pages):
                data = self._fetch(url, proxy_country)
                for raw in data.get("items") or []:
                    if not isinstance(raw, dict):
                        continue
                    vehicle = normalize_item(raw)
                    key = vehicle.listing_id or vehicle.vin or vehicle.url or vehicle.title
                    if key is None or key in seen:
                        continue
                    seen.add(key)
                    vehicles.append(vehicle)
                    if limit is not None and len(vehicles) >= limit:
                        return vehicles
                url = data.get("next_page")
                page += 1
        return vehicles


def vehicles_to_dicts(vehicles: Sequence[Vehicle]) -> list[dict[str, Any]]:
    return [v.to_dict() for v in vehicles]


def to_json(vehicles: Sequence[Vehicle], *, indent: int | None = 2) -> str:
    return json.dumps(vehicles_to_dicts(vehicles), indent=indent, ensure_ascii=False)


def to_csv(vehicles: Sequence[Vehicle], path: str) -> None:
    """Write ``vehicles`` to a CSV file at ``path``."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(FIELDNAMES))
        writer.writeheader()
        for vehicle in vehicles:
            writer.writerow(vehicle.to_dict())
