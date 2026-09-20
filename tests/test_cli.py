"""Offline tests for the argparse CLI, with AutotraderScraper monkeypatched."""

from __future__ import annotations

import json

import pytest

from autotrader_scraper import Vehicle, cli


class StubScraper:
    """Replaces AutotraderScraper; records the scrape() kwargs it was called with."""

    last_kwargs: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    def scrape(self, queries, **kwargs):
        StubScraper.last_kwargs = {"queries": list(queries), **kwargs}
        return [
            Vehicle(title="2020 Honda Accord", make="Honda", model="Accord", price=22250.0,
                    currency="USD", mileage=53849, mileage_unit="mi"),
            Vehicle(title="2016 Toyota Tacoma", make="Toyota", model="Tacoma", price=24180.0,
                    currency="USD"),
        ]


@pytest.fixture(autouse=True)
def _patch_scraper(monkeypatch):
    monkeypatch.setattr(cli, "AutotraderScraper", StubScraper)


def test_parser_defaults():
    args = cli.build_parser().parse_args(["toyota tacoma"])
    assert args.queries == ["toyota tacoma"]
    assert args.country == "US"
    assert args.pages == 1
    assert args.format == "json"
    assert args.zip_code is None


def test_parser_accepts_multiple_queries_and_flags():
    argv = ["honda civic", "toyota corolla", "-z", "78701", "-r", "100", "-p", "2", "-n", "60"]
    args = cli.build_parser().parse_args(argv)
    assert args.queries == ["honda civic", "toyota corolla"]
    assert args.zip_code == "78701"
    assert args.radius == 100
    assert args.pages == 2
    assert args.limit == 60


def test_json_output_to_stdout(capsys):
    rc = cli.main(["toyota tacoma", "--zip", "78701"])
    assert rc == 0
    out = capsys.readouterr().out
    rows = json.loads(out)
    assert rows[0]["make"] == "Honda"
    assert StubScraper.last_kwargs["proxy_country"] == "US"
    assert StubScraper.last_kwargs["zip_code"] == "78701"


def test_json_output_to_file(tmp_path):
    out = tmp_path / "out.json"
    rc = cli.main(["honda civic", "--output", str(out), "--pretty"])
    assert rc == 0
    rows = json.loads(out.read_text(encoding="utf-8"))
    assert len(rows) == 2


def test_csv_requires_output():
    rc = cli.main(["honda civic", "--format", "csv"])
    assert rc == 2


def test_csv_output_to_file(tmp_path):
    out = tmp_path / "out.csv"
    rc = cli.main(["honda civic", "--format", "csv", "--output", str(out)])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "title,year,make" in text.replace(" ", "")
    assert "2020 Honda Accord" in text
