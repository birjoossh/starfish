"""Tests for morning digest."""

from __future__ import annotations

from datetime import date

import pytest

from nifty50.digest import generate_digest


class TestDigest:
    def test_generate_digest(self):
        output = generate_digest(trade_date=date(2024, 1, 17))

        assert "Nifty 50 Daily Digest" in output
        assert "Top Gainers" in output
        assert "Top Losers" in output
        assert "Watchlist" in output

    def test_digest_shows_watchlist_stars(self):
        output = generate_digest(trade_date=date(2024, 1, 17))

        # RELIANCE is in watchlist, should have ★
        assert "RELIANCE" in output
        assert "★" in output

    def test_digest_no_data(self):
        output = generate_digest(trade_date=date(2099, 1, 1))
        assert "No signal data" in output
