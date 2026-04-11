"""Tests for watchlist module."""

from __future__ import annotations

import pytest
import yaml

from dashboard.watchlist import load_watchlist


class TestWatchlist:
    def test_load_existing_watchlist(self, tmp_path, monkeypatch):
        wl_path = tmp_path / "watchlist.yaml"
        wl_path.write_text(yaml.dump({"symbols": ["RELIANCE", "HDFCBANK"]}))

        monkeypatch.setattr("dashboard.watchlist.settings._watchlist_path_override", str(wl_path), raising=False)

        # Monkeypatch the property via the class
        from config.settings import Settings
        monkeypatch.setattr(
            Settings, "watchlist_path",
            property(lambda self: tmp_path / "watchlist.yaml")
        )

        result = load_watchlist()
        assert "RELIANCE" in result
        assert "HDFCBANK" in result
        assert len(result) == 2

    def test_missing_watchlist(self, tmp_path, monkeypatch):
        from config.settings import Settings
        monkeypatch.setattr(
            Settings, "watchlist_path",
            property(lambda self: tmp_path / "nonexistent.yaml")
        )

        result = load_watchlist()
        assert result == set()

    def test_invalid_yaml(self, tmp_path, monkeypatch):
        wl_path = tmp_path / "watchlist.yaml"
        wl_path.write_text("{{invalid yaml: [}]]")

        from config.settings import Settings
        monkeypatch.setattr(
            Settings, "watchlist_path",
            property(lambda self: wl_path)
        )

        result = load_watchlist()
        assert result == set()

    def test_missing_symbols_key(self, tmp_path, monkeypatch):
        wl_path = tmp_path / "watchlist.yaml"
        wl_path.write_text(yaml.dump({"other_key": "value"}))

        from config.settings import Settings
        monkeypatch.setattr(
            Settings, "watchlist_path",
            property(lambda self: wl_path)
        )

        result = load_watchlist()
        assert result == set()
