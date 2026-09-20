"""Offline tests for URL building and item normalization.

Samples are trimmed from real Autotrader parsed responses, to lock in the
normalizing behaviour: the schema.org condition URL, the grouped mileage string
with its separate unit code, the null per-item currency, the drivetrain landing
under either ``drive_type`` or ``drive_wheel_configuration``, and the dealer
location that only appears in the description prose.
"""

from __future__ import annotations

import json

from autotrader_scraper import build_search_url, normalize_item, to_json
from autotrader_scraper.scraper import (
    _condition,
    _int,
    _location,
    _price_number,
    _year,
)

# A listing that reports the drivetrain under `drive_wheel_configuration`.
ACCORD_ITEM = {
    "title": "Certified 2020 Honda Accord Sport",
    "url": "https://www.autotrader.com/cars-for-sale/vehicle/790959375",
    "image": "https://images.autotrader.com/hn/c/2fbc3642cc0d417d8d71741caf84f9a6.jpg",
    "vin": "1HGCV1F30LA113758",
    "year": 2020,
    "make": "Honda",
    "model": "Accord",
    "condition": "http://schema.org/UsedCondition",
    "price": {"value": 22250, "currency": None},
    "price_currency": None,
    "mileage": "53,849",
    "mileage_unit": "SMI",
    "engine": "30L",
    "transmission": "Continuously Variable Automatic",
    "fuel_type": "Gasoline",
    "exterior_color": "Silver",
    "interior_color": "Black",
    "drive_wheel_configuration": "2 Wheel Drive - Front",
    "fuel_efficiency": "Gasoline",  # redundant echo of fuel_type -> dropped
    "description": "Location: Los Angeles, CA. This 2020 Honda Accord is listed for $22250",
    "dealer_name": "Airport Marina Honda",
    "listing_id": 790959375,
}

# A listing that reports the drivetrain under `drive_type` and carries a trim.
TACOMA_ITEM = {
    "title": "Used 2016 Toyota Tacoma SR5 w/ Towing Package",
    "url": "https://www.autotrader.com/cars-for-sale/vehicle/791374637",
    "image": "https://images.autotrader.com/hn/c/5d469f66b26249658b8d19d44c838d72.jpg",
    "price": {"value": 24180, "currency": None},
    "price_currency": None,
    "year": 2016,
    "make": "Toyota",
    "model": "Tacoma",
    "trim": "SR5",
    "vin": "5TFAZ5CN1GX009953",
    "mileage": "87,165",
    "mileage_unit": "SMI",
    "engine": "6-Cylinder",
    "transmission": "6-Speed Automatic",
    "drive_type": "2 Wheel Drive - Rear",
    "exterior_color": "Gray",
    "interior_color": "Gray",
    "fuel_type": "Gasoline",
    "condition": "http://schema.org/UsedCondition",
    "dealer_name": "AutoNation Toyota South Austin",
    "listing_id": 791374637,
}


def test_build_search_url_make_model():
    assert (
        build_search_url("toyota tacoma")
        == "https://www.autotrader.com/cars-for-sale/toyota/tacoma"
    )


def test_build_search_url_make_only_and_hyphenated_model():
    assert build_search_url("ford") == "https://www.autotrader.com/cars-for-sale/ford"
    assert (
        build_search_url("ford f-150") == "https://www.autotrader.com/cars-for-sale/ford/f-150"
    )


def test_build_search_url_all_and_params():
    assert build_search_url("all") == "https://www.autotrader.com/cars-for-sale/all-cars"
    assert (
        build_search_url("honda civic", zip_code="78701", radius=100)
        == "https://www.autotrader.com/cars-for-sale/honda/civic?zip=78701&searchRadius=100"
    )


def test_build_search_url_passes_through_full_url():
    url = "https://www.autotrader.com/cars-for-sale/tesla/model-3?page=2"
    assert build_search_url(url) == url
    assert build_search_url("  " + url + "  ") == url
    # zip/radius are ignored for a full URL rather than corrupting it.
    assert build_search_url(url, zip_code="90210", radius=50) == url


def test_normalize_accord_item():
    v = normalize_item(ACCORD_ITEM)
    assert v.year == 2020
    assert v.make == "Honda"
    assert v.model == "Accord"
    assert v.condition == "Used"  # decoded from the schema.org URL
    assert v.price == 22250.0
    assert v.currency == "USD"  # parser leaves currency null; we stamp USD
    assert v.mileage == 53849  # grouped string parsed to int
    assert v.mileage_unit == "mi"  # SMI -> mi
    assert v.vin == "1HGCV1F30LA113758"
    assert v.drivetrain == "2 Wheel Drive - Front"  # from drive_wheel_configuration
    assert v.location == "Los Angeles, CA"  # lifted from the description
    assert v.dealer_name == "Airport Marina Honda"
    assert v.listing_id == "790959375"


def test_normalize_tacoma_item_drive_type_and_trim():
    v = normalize_item(TACOMA_ITEM)
    assert v.trim == "SR5"
    assert v.drivetrain == "2 Wheel Drive - Rear"  # from drive_type this time
    assert v.mileage == 87165
    assert v.location is None  # this row has no description
    assert v.listing_id == "791374637"


def test_mileage_unit_defaults_to_miles_when_omitted():
    # The parser sometimes drops the unit code; a US reading is miles.
    v = normalize_item({"title": "2019 Kia Sportage", "mileage": "41,002"})
    assert v.mileage == 41002
    assert v.mileage_unit == "mi"
    # ...but no reading means no invented unit.
    assert normalize_item({"title": "2019 Kia Sportage"}).mileage_unit is None


def test_price_number_forms():
    assert _price_number({"value": 22250, "currency": None}) == 22250.0
    assert _price_number("$24,180") == 24180.0
    assert _price_number(19999) == 19999.0
    assert _price_number("Call for price") is None
    assert _price_number(None) is None


def test_int_and_year_helpers():
    assert _int("53,849") == 53849
    assert _int(1200) == 1200
    assert _int("N/A") is None
    assert _year(2020) == 2020
    assert _year("2016") == 2016
    assert _year(53849) is None  # a mileage value is not a plausible model year
    assert _year(None) is None


def test_condition_decoding():
    assert _condition("http://schema.org/UsedCondition") == "Used"
    assert _condition("http://schema.org/NewCondition") == "New"
    assert _condition("Certified Pre-Owned") == "Certified"
    assert _condition("") is None
    assert _condition(None) is None


def test_location_extraction():
    assert _location("Location: Austin, TX. Great truck.") == "Austin, TX"
    assert _location("No location here") is None
    assert _location(None) is None


def test_listing_id_falls_back_to_url():
    v = normalize_item(
        {
            "title": "2018 Subaru Outback",
            "url": "https://www.autotrader.com/cars-for-sale/vehicle/700000001",
        }
    )
    assert v.listing_id == "700000001"


def test_to_json_is_valid_and_ordered():
    text = to_json([normalize_item(ACCORD_ITEM)])
    rows = json.loads(text)
    assert rows[0]["make"] == "Honda"
    assert rows[0]["price"] == 22250.0
    assert rows[0]["mileage"] == 53849
    assert rows[0]["listing_id"] == "790959375"
