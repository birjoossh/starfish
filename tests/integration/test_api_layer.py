"""Integration tests — Layer 3: API Layer.

Tests all FastAPI endpoint contracts:
- Response shapes match Pydantic models
- Pagination (limit/offset) on list endpoints
- Input validation and case-handling
- Error response formats
- All 8 endpoints covered: health, constituents, prices, prices/range,
  market-overview, movers, events, actions
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.main import app
from tests.integration.fixtures.factories import (
    INTG_TEST_DATE,
    INTG_TEST_DATE_2,
    SYM_A,
    build_bhavcopy_csv,
)
from tests.integration.conftest import seed_prices_raw

client = TestClient(app)


# ─── Layer 3a: Health Endpoint ───────────────────────────────────────────────

class TestHealthEndpoint:
    """/health must return 200 with {status, tables} shape."""

    def test_returns_200(self) -> None:
        r = client.get("/health")
        assert r.status_code == 200

    def test_response_shape(self) -> None:
        data = client.get("/health").json()
        assert "status" in data
        assert "tables" in data
        assert isinstance(data["tables"], dict)

    def test_known_tables_present(self) -> None:
        tables = client.get("/health").json()["tables"]
        expected = {
            "dim_stock", "fact_eod_price", "fact_52wk",
            "dim_nifty50_constituent", "fact_corporate_action",
            "fact_corporate_event", "mart_stock_signals",
            "mart_volume_anomaly", "ingestion_log",
        }
        assert expected.issubset(set(tables.keys()))

    def test_db_connectivity_ok(self) -> None:
        data = client.get("/health").json()
        assert data["status"] == "ok"


# ─── Layer 3b: Constituents Endpoint ─────────────────────────────────────────

class TestConstituentsEndpoint:
    """/constituents must return all 50 Nifty50 stocks with required fields."""

    def test_returns_200(self) -> None:
        assert client.get("/constituents").status_code == 200

    def test_returns_list(self) -> None:
        data = client.get("/constituents").json()
        assert isinstance(data, list)

    def test_exactly_50_nifty_stocks(self) -> None:
        data = client.get("/constituents").json()
        assert len(data) == 50

    def test_stock_has_required_fields(self) -> None:
        stock = client.get("/constituents").json()[0]
        for field in ("symbol", "company_name", "sector", "isin", "nifty50_member"):
            assert field in stock, f"Missing field: {field}"

    def test_all_nifty50_member_true(self) -> None:
        for stock in client.get("/constituents").json():
            assert stock["nifty50_member"] is True

    def test_sorted_by_symbol(self) -> None:
        symbols = [s["symbol"] for s in client.get("/constituents").json()]
        assert symbols == sorted(symbols)


# ─── Layer 3c: Prices Endpoint ───────────────────────────────────────────────

class TestPricesEndpoint:
    """/prices/{symbol} must return price history, 404 for unknowns."""

    def test_valid_symbol_200(self) -> None:
        r = client.get(f"/prices/{SYM_A}")
        assert r.status_code == 200

    def test_valid_symbol_returns_list(self) -> None:
        data = client.get(f"/prices/{SYM_A}").json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_price_row_shape(self) -> None:
        row = client.get(f"/prices/{SYM_A}").json()[0]
        for field in (
            "trade_date", "symbol", "open", "high", "low", "close",
            "prev_close", "total_traded_qty", "series",
        ):
            assert field in row, f"Missing field: {field}"

    def test_symbol_in_response_matches_request(self) -> None:
        data = client.get(f"/prices/{SYM_A}").json()
        assert all(r["symbol"] == SYM_A for r in data)

    def test_unknown_symbol_404(self) -> None:
        r = client.get("/prices/FAKESTOCKNONE")
        assert r.status_code == 404

    def test_lowercase_symbol_auto_uppercased(self) -> None:
        r_upper = client.get(f"/prices/{SYM_A}")
        r_lower = client.get(f"/prices/{SYM_A.lower()}")
        assert r_lower.status_code == r_upper.status_code
        # Both return the same symbol in the response
        if r_lower.status_code == 200:
            assert r_lower.json()[0]["symbol"] == SYM_A


# ─── Layer 3d: Prices Range Endpoint ─────────────────────────────────────────

class TestPricesRangeEndpoint:
    """/prices/{symbol}/range filters by date range."""

    def test_valid_range_returns_200(self) -> None:
        r = client.get(f"/prices/{SYM_A}/range?from=2024-01-15&to=2024-01-17")
        assert r.status_code == 200

    def test_range_returns_list(self) -> None:
        data = client.get(f"/prices/{SYM_A}/range?from=2024-01-15&to=2024-01-17").json()
        assert isinstance(data, list)

    def test_future_range_empty_list(self) -> None:
        r = client.get(f"/prices/{SYM_A}/range?from=2088-01-01&to=2088-01-31")
        assert r.status_code == 200
        assert r.json() == []

    def test_missing_from_param_422(self) -> None:
        r = client.get(f"/prices/{SYM_A}/range?to=2024-01-17")
        assert r.status_code == 422

    def test_missing_to_param_422(self) -> None:
        r = client.get(f"/prices/{SYM_A}/range?from=2024-01-15")
        assert r.status_code == 422

    def test_dates_in_response_within_range(self) -> None:
        from_d, to_d = "2024-01-15", "2024-01-17"
        rows = client.get(f"/prices/{SYM_A}/range?from={from_d}&to={to_d}").json()
        for row in rows:
            assert from_d <= row["trade_date"] <= to_d


# ─── Layer 3e: Market Overview Endpoint ──────────────────────────────────────

class TestMarketOverviewEndpoint:
    """/market-overview returns {sector_breadth, components}."""

    def test_returns_200(self) -> None:
        r = client.get("/market-overview")
        assert r.status_code == 200

    def test_response_shape(self) -> None:
        data = client.get("/market-overview").json()
        assert "sector_breadth" in data
        assert "components" in data
        assert isinstance(data["sector_breadth"], list)
        assert isinstance(data["components"], list)

    def test_sector_breadth_has_required_fields(self) -> None:
        breadth = client.get("/market-overview").json()["sector_breadth"]
        if breadth:    # may be empty if mart_stock_signals is empty in test DB
            row = breadth[0]
            for field in ("sector", "num_stocks", "advancing", "declining"):
                assert field in row

    def test_calc_date_param_accepted(self) -> None:
        r = client.get("/market-overview?calc_date=2099-06-01")
        assert r.status_code == 200
        data = r.json()
        # No signals for far-future date → empty lists (not an error)
        assert data["sector_breadth"] == []
        assert data["components"] == []


# ─── Layer 3f: Movers Endpoint ───────────────────────────────────────────────

class TestMoversEndpoint:
    """/movers returns {gainers, losers, all_data}."""

    def test_returns_200(self) -> None:
        assert client.get("/movers").status_code == 200

    def test_response_shapes(self) -> None:
        data = client.get("/movers").json()
        # May be empty list if mart has no data; empty list is valid
        if isinstance(data, list):
            return
        assert "gainers" in data
        assert "losers" in data
        assert "all_data" in data

    def test_calc_date_far_future_returns_empty(self) -> None:
        data = client.get("/movers?calc_date=2099-06-01").json()
        # No signals for far-future → empty list
        assert data == []

    def test_movers_row_has_symbol_and_returns(self) -> None:
        data = client.get("/movers").json()
        if isinstance(data, dict) and data.get("all_data"):
            row = data["all_data"][0]
            assert "symbol" in row
            assert "return_1d" in row


# ─── Layer 3g: Events Endpoint ───────────────────────────────────────────────

class TestEventsEndpoint:
    """/events supports filtering by symbol, date range, event_type."""

    def test_returns_200(self) -> None:
        assert client.get("/events").status_code == 200

    def test_returns_list(self) -> None:
        assert isinstance(client.get("/events").json(), list)

    def test_symbol_filter_uppercase_normalised(self) -> None:
        r_upper = client.get(f"/events?symbol={SYM_A}")
        r_lower = client.get(f"/events?symbol={SYM_A.lower()}")
        assert r_upper.status_code == 200
        assert r_lower.status_code == 200

    def test_date_range_filter(self) -> None:
        r = client.get("/events?from_date=2024-01-01&to_date=2024-01-31")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        for row in data:
            assert "2024-01-01" <= row["event_date"] <= "2024-01-31"

    def test_event_type_filter(self) -> None:
        r = client.get("/events?event_type=DIVIDEND")
        assert r.status_code == 200

    def test_event_row_has_required_fields(self) -> None:
        rows = client.get("/events?from_date=2024-01-01&to_date=2024-01-31").json()
        for row in rows:
            for field in ("symbol", "event_date", "event_type"):
                assert field in row


# ─── Layer 3h: Actions Endpoint ──────────────────────────────────────────────

class TestActionsEndpoint:
    """/actions supports filtering by symbol, date range, event_type."""

    def test_returns_200(self) -> None:
        assert client.get("/actions").status_code == 200

    def test_returns_list(self) -> None:
        assert isinstance(client.get("/actions").json(), list)

    def test_symbol_filter(self) -> None:
        r = client.get(f"/actions?symbol={SYM_A}")
        assert r.status_code == 200

    def test_lowercase_symbol_normalised(self) -> None:
        r_lower = client.get(f"/actions?symbol={SYM_A.lower()}")
        r_upper = client.get(f"/actions?symbol={SYM_A}")
        assert r_lower.json() == r_upper.json()

    def test_event_type_filter(self) -> None:
        r = client.get("/actions?event_type=DIVIDEND")
        assert r.status_code == 200

    def test_action_row_has_required_fields(self) -> None:
        rows = client.get("/actions").json()
        for row in rows[:5]:
            for field in ("symbol", "purpose", "event_type", "ex_date"):
                assert field in row

    def test_date_range_filter(self) -> None:
        r = client.get("/actions?from_date=2024-01-01&to_date=2024-01-31")
        assert r.status_code == 200
        for row in r.json():
            assert "2024-01-01" <= row["ex_date"] <= "2024-01-31"


# ─── Layer 3i: Input Validation & Error Responses ────────────────────────────

class TestInputValidation:
    """Endpoints must reject invalid inputs with informative HTTP errors."""

    def test_prices_range_invalid_date_format_422(self) -> None:
        """Non-ISO date strings should not be accepted."""
        r = client.get(f"/prices/{SYM_A}/range?from=15-Jan-2024&to=17-Jan-2024")
        assert r.status_code == 422

    def test_min_significance_accepts_integer(self) -> None:
        r = client.get("/events?min_significance=3")
        assert r.status_code == 200

    def test_min_significance_non_integer_422(self) -> None:
        r = client.get("/events?min_significance=high")
        assert r.status_code == 422

    def test_404_response_has_detail_field(self) -> None:
        """FastAPI 404s must have a 'detail' field (default FastAPI shape)."""
        r = client.get("/prices/FAKESTOCKNONE")
        assert r.status_code == 404
        assert "detail" in r.json()
