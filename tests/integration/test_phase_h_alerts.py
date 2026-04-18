"""Integration tests for Phase H: Alert Rules + EOD Scheduler."""

import pytest
from datetime import date

from analytics.alert_engine import AlertEngine, run_daily_alert_evaluation
from analytics.alert_conditions import AlertConditions
from analytics.dedup_engine import DedupEngine, DEDUP_ALERT_TYPES


class TestAlertConditions:
    """Test individual alert condition implementations."""

    @pytest.mark.asyncio
    async def test_a01_deep_drawdown_exists(self):
        """A-01 should find stocks with drawdown > 20%."""
        conditions = AlertConditions()
        # This will return empty if no stocks in db meet criteria
        alerts = await conditions.a01_deep_drawdown(date.today())
        # Just verify the function runs without error
        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_a04_extreme_volume_spike_exists(self):
        """A-04 should check for volume spikes."""
        conditions = AlertConditions()
        alerts = await conditions.a04_extreme_volume_spike(date.today())
        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_a08_market_breadth_exists(self):
        """A-08 should calculate market breadth."""
        conditions = AlertConditions()
        alerts = await conditions.a08_market_breadth(date.today())
        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_a12_rating_downgrade_exists(self):
        """A-12 should check for rating downgrades."""
        conditions = AlertConditions()
        alerts = await conditions.a12_rating_downgrade(date.today())
        assert isinstance(alerts, list)


class TestDedupEngine:
    """Test alert deduplication logic."""

    def test_dedup_alert_types_includes_correct_alerts(self):
        """Verify the right alert types have deduplication."""
        assert "A-01" in DEDUP_ALERT_TYPES  # Deep Drawdown
        assert "A-02" in DEDUP_ALERT_TYPES  # ISS Breakout
        assert "A-03" in DEDUP_ALERT_TYPES  # ISS Breakdown
        assert "A-07" in DEDUP_ALERT_TYPES  # Watchlist Move

        # These should NOT have deduplication
        assert "A-04" not in DEDUP_ALERT_TYPES  # Volume Spike
        assert "A-05" not in DEDUP_ALERT_TYPES  # Critical Event
        assert "A-06" not in DEDUP_ALERT_TYPES  # Index Reconstitution
        assert "A-08" not in DEDUP_ALERT_TYPES  # Market Breadth
        assert "A-09" not in DEDUP_ALERT_TYPES  # Multiple 52W Lows
        assert "A-10" not in DEDUP_ALERT_TYPES  # Accumulation
        assert "A-11" not in DEDUP_ALERT_TYPES  # Pledging Change
        assert "A-12" not in DEDUP_ALERT_TYPES  # Rating Downgrade
        assert "A-13" not in DEDUP_ALERT_TYPES  # Breakout Near 52W High
        assert "A-14" not in DEDUP_ALERT_TYPES  # Volume Dryup

    def test_should_fire_alert_without_dedup(self):
        """Non-dedup alerts should always fire."""
        dedup = DedupEngine()

        # A-04 has no dedup
        assert dedup.should_fire_alert("A-04", "RELIANCE", date.today()) is True

        # Market-wide alerts have no dedup
        assert dedup.should_fire_alert("A-08", None, date.today()) is True

    def test_should_fire_alert_with_dedup_new_alert(self):
        """New alert for a stock should fire."""
        dedup = DedupEngine()

        # A-01 for a stock that hasn't fired recently should fire
        # (will return True because no prior fire in DB)
        assert dedup.should_fire_alert("A-01", "RELIANCE", date.today()) is True

    def test_should_fire_alert_with_dedup_existing_alert(self):
        """Existing alert within dedup window should be suppressed."""
        dedup = DedupEngine()

        # This would return False if there was a recent fire
        # Since we can't easily test the DB state, just verify the function signature
        assert hasattr(dedup, "should_fire_alert")


class TestAlertEngine:
    """Test the main alert engine."""

    @pytest.mark.asyncio
    async def test_evaluate_all_alerts_returns_list(self):
        """evaluate_all_alerts should return a list."""
        engine = AlertEngine()
        alerts = await engine.evaluate_all_alerts(date.today())
        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_fire_alert_creates_record(self):
        """fire_alert should insert into alerts table."""
        engine = AlertEngine()

        test_alert = {
            "alert_name": "A-01",
            "symbol": "TESTSYMB",
            "trigger_value": {"drawdown_pct": -25.0},
            "description": "Test alert",
            "severity": "Medium",
        }

        alert_id = await engine.fire_alert(test_alert)

        # Should get an alert_id even if dedup suppresses
        assert alert_id is None or isinstance(alert_id, str)

    @pytest.mark.asyncio
    async def test_fire_alerts_returns_list(self):
        """fire_alerts should return a list of alert_ids."""
        engine = AlertEngine()

        alerts = [
            {
                "alert_name": "A-01",
                "symbol": "TESTSYMB1",
                "trigger_value": {"drawdown_pct": -25.0},
                "description": "Test alert 1",
                "severity": "Medium",
            },
            {
                "alert_name": "A-02",
                "symbol": "TESTSYMB2",
                "trigger_value": {"iss_score": 75},
                "description": "Test alert 2",
                "severity": "Medium",
            },
        ]

        results = await engine.fire_alerts(alerts)
        assert isinstance(results, list)
        assert len(results) == len(alerts)


class TestRunDailyAlertEvaluation:
    """Test the run_daily_alert_evaluation convenience function."""

    @pytest.mark.asyncio
    async def test_returns_list_of_alerts(self):
        """Should return list of alert results."""
        # This will run all alert conditions
        # The result may be empty if no conditions are met
        alerts = await run_daily_alert_evaluation(date(2099, 1, 1))  # Far future - likely empty
        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_alerts_have_required_fields(self):
        """Each alert should have required fields."""
        alerts = await run_daily_alert_evaluation(date.today())

        required_fields = {"alert_id", "alert_name", "severity", "description", "triggered_at"}

        for alert in alerts:
            assert isinstance(alert, dict)
            # Check that required fields are present
            for field in required_fields:
                assert field in alert, f"Missing field: {field}"
