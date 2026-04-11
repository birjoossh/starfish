"""Load threshold configuration from config.yaml.

All signal thresholds, window sizes, and classification boundaries
live in config/config.yaml — not in code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from config.settings import settings


def load_config() -> dict[str, Any]:
    """Load config.yaml and return as dict."""
    path = settings.config_yaml_path
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


_config_cache: dict[str, Any] | None = None


def get_config() -> dict[str, Any]:
    """Get cached config, loading on first call."""
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


def get_series_filter() -> list[str]:
    """Return list of NSE series codes to ingest."""
    return get_config().get("series_filter", ["EQ", "BE", "BL", "SM", "ST"])


def get_return_windows() -> dict[str, int]:
    """Return trading-day windows for return computation."""
    return get_config().get("returns", {
        "short_window": 1,
        "medium_window": 21,
        "long_window": 63,
        "yearly_window": 252,
    })


def get_volume_thresholds() -> dict[str, float]:
    """Return volume spike classification thresholds."""
    return get_config().get("volume", {
        "avg_window_days": 20,
        "long_avg_window_days": 60,
        "spike_mild": 1.2,
        "spike_moderate": 1.5,
        "spike_high": 2.0,
        "spike_extreme": 3.0,
    })


def get_fifty_two_week_lookback() -> int:
    """Return 52-week lookback in trading days."""
    return get_config().get("fifty_two_week", {}).get("lookback_days", 252)
