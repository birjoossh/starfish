"""Tests for FastAPI endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "tables" in data


class TestConstituentsEndpoint:
    def test_constituents_returns_list(self):
        r = client.get("/constituents")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 50

    def test_constituent_has_required_fields(self):
        r = client.get("/constituents")
        stock = r.json()[0]
        assert "symbol" in stock
        assert "company_name" in stock
        assert "sector" in stock
        assert "isin" in stock


class TestPricesEndpoint:
    def test_prices_valid_symbol(self):
        r = client.get("/prices/RELIANCE")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert data[0]["symbol"] == "RELIANCE"

    def test_prices_unknown_symbol(self):
        r = client.get("/prices/FAKESYMBOL")
        assert r.status_code == 404

    def test_prices_lowercase_symbol(self):
        r = client.get("/prices/reliance")
        assert r.status_code == 200  # Should uppercase internally


class TestPricesRangeEndpoint:
    def test_valid_range(self):
        r = client.get("/prices/RELIANCE/range?from=2024-01-16&to=2024-01-17")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2

    def test_range_no_data(self):
        r = client.get("/prices/RELIANCE/range?from=2025-01-01&to=2025-01-31")
        assert r.status_code == 200
        assert len(r.json()) == 0
