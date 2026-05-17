"""Tests for volume anomaly engine — VA-1 through VA-7 rule matching."""

from __future__ import annotations

import pytest
from analytics.compute_volume_anomalies import _match_va_rule, _classify_spike


class TestSpikeClassification:
    def test_normal_below_mild(self):
        assert _classify_spike(1.0, {}) == "Normal"

    def test_mild_boundary(self):
        assert _classify_spike(1.2, {}) == "Mild"

    def test_moderate_boundary(self):
        assert _classify_spike(1.5, {}) == "Moderate"

    def test_high_boundary(self):
        assert _classify_spike(2.0, {}) == "High"

    def test_extreme_boundary(self):
        assert _classify_spike(3.0, {}) == "Extreme"

    def test_custom_thresholds(self):
        t = {"spike_extreme": 4.0, "spike_high": 3.0, "spike_moderate": 2.0, "spike_mild": 1.5}
        assert _classify_spike(3.5, t) == "High"
        assert _classify_spike(4.0, t) == "Extreme"


class TestVARuleMatching:
    """VA rules per spec §6.3, evaluated in priority order (first match wins)."""

    # --- VA-5: vol > 3.0 AND event within ±3 days ---

    def test_va5_event_driven(self):
        result = _match_va_rule(
            volume_ratio=3.5, price_chg=0.05,
            delivery_pct=None, has_event_within_3d=True, dry_count_5d=0,
        )
        assert result == "VA-5 Event-Driven Volume"

    def test_va5_not_without_event(self):
        result = _match_va_rule(
            volume_ratio=3.5, price_chg=0.05,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result != "VA-5 Event-Driven Volume"

    # --- VA-1: vol > 2.0 AND price_chg > +3% ---

    def test_va1_bullish_surge(self):
        result = _match_va_rule(
            volume_ratio=2.5, price_chg=0.05,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result == "VA-1 Bullish Volume Surge"

    def test_va1_not_at_threshold(self):
        result = _match_va_rule(
            volume_ratio=2.5, price_chg=0.03,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result != "VA-1 Bullish Volume Surge"  # must be strictly > 3%

    # --- VA-2: vol > 2.0 AND price_chg < -3% ---

    def test_va2_distribution(self):
        result = _match_va_rule(
            volume_ratio=2.5, price_chg=-0.05,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result == "VA-2 Distribution Signal"

    # --- VA-3: vol > 2.0 AND ABS(price_chg) < 1% ---

    def test_va3_unclear(self):
        result = _match_va_rule(
            volume_ratio=2.5, price_chg=0.005,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result == "VA-3 A/D Unclear — Watch"

    def test_va3_boundary_just_under(self):
        result = _match_va_rule(
            volume_ratio=2.1, price_chg=0.009,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result == "VA-3 A/D Unclear — Watch"

    # --- VA-6: vol > 1.5 AND delivery_pct > 60% ---

    def test_va6_institutional(self):
        result = _match_va_rule(
            volume_ratio=1.8, price_chg=0.0,
            delivery_pct=65.0, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result == "VA-6 Institutional Accumulation"

    def test_va6_not_with_null_delivery(self):
        result = _match_va_rule(
            volume_ratio=1.8, price_chg=0.0,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result != "VA-6 Institutional Accumulation"

    # --- VA-7: vol > 1.5 AND delivery_pct < 25% ---

    def test_va7_speculative(self):
        result = _match_va_rule(
            volume_ratio=1.8, price_chg=0.0,
            delivery_pct=20.0, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result == "VA-7 Speculative Activity"

    # --- VA-4: vol < 0.4 for 5+ consecutive sessions ---

    def test_va4_drying_up(self):
        result = _match_va_rule(
            volume_ratio=0.35, price_chg=0.0,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=5,
        )
        assert result == "VA-4 Drying Up — Breakout Setup"

    def test_va4_not_at_4_days(self):
        result = _match_va_rule(
            volume_ratio=0.35, price_chg=0.0,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=4,
        )
        assert result is None

    def test_va4_not_at_ratio_above_threshold(self):
        result = _match_va_rule(
            volume_ratio=0.45, price_chg=0.0,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=5,
        )
        assert result is None

    # --- Priority ordering ---

    def test_va5_beats_va1(self):
        """When both VA-5 and VA-1 conditions are met, VA-5 wins (evaluated first)."""
        result = _match_va_rule(
            volume_ratio=3.5, price_chg=0.05,
            delivery_pct=None, has_event_within_3d=True, dry_count_5d=0,
        )
        assert result == "VA-5 Event-Driven Volume"

    def test_va1_beats_va6(self):
        """VA-1 (vol>2, price>3%) beats VA-6 (vol>1.5, delivery>60%)."""
        result = _match_va_rule(
            volume_ratio=2.5, price_chg=0.05,
            delivery_pct=70.0, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result == "VA-1 Bullish Volume Surge"

    def test_normal_no_match(self):
        result = _match_va_rule(
            volume_ratio=1.1, price_chg=0.01,
            delivery_pct=50.0, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result is None

    # --- Edge cases ---

    def test_negative_volume_ratio(self):
        """Should not crash on negative ratio."""
        result = _match_va_rule(
            volume_ratio=-0.5, price_chg=0.0,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result is None

    def test_large_positive_price_chg(self):
        result = _match_va_rule(
            volume_ratio=2.5, price_chg=0.15,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result == "VA-1 Bullish Volume Surge"

    def test_va1_barely_above_vol_threshold(self):
        """Volume ratio just above 2.0 with price > 3% should match VA-1."""
        result = _match_va_rule(
            volume_ratio=2.001, price_chg=0.04,
            delivery_pct=None, has_event_within_3d=False, dry_count_5d=0,
        )
        assert result == "VA-1 Bullish Volume Surge"
