"""EOD batch scheduler using APScheduler.

Schedules daily jobs for signal computation and alert evaluation.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from analytics.alert_engine import AlertEngine
from analytics.compute_signals import SignalComputer
from config.settings import settings

logger = logging.getLogger(__name__)

# IST timezone
IST = ZoneInfo("Asia/Kolkata")


class EODScheduler:
    """Manage EOD batch jobs for the dashboard."""

    def __init__(self, db_url: Optional[str] = None):
        self.scheduler = AsyncIOScheduler(timezone=IST)
        self.db_url = db_url or settings.db_url
        self.alert_engine: Optional[AlertEngine] = None
        self.signal_computer: Optional[SignalComputer] = None
        self._started = False

    def start(self) -> None:
        """Start the scheduler and register all jobs."""
        if self._started:
            logger.warning("Scheduler already started")
            return

        # Initialize components
        self.alert_engine = AlertEngine()
        self.signal_computer = SignalComputer(self.db_url)

        # Schedule signal computation (6:30 PM IST)
        self.scheduler.add_job(
            self._run_signal_computation,
            CronTrigger(hour=18, minute=30, timezone=IST),
            id="signal_computation",
            replace_existing=True,
        )
        logger.info("Scheduled signal computation at 18:30 IST")

        # Schedule alert evaluation (7:00 PM IST)
        self.scheduler.add_job(
            self._run_alert_evaluation,
            CronTrigger(hour=19, minute=0, timezone=IST),
            id="alert_evaluation",
            replace_existing=True,
        )
        logger.info("Scheduled alert evaluation at 19:00 IST")

        # Schedule market overview refresh (7:30 PM IST)
        self.scheduler.add_job(
            self._run_market_refresh,
            CronTrigger(hour=19, minute=30, timezone=IST),
            id="market_refresh",
            replace_existing=True,
        )
        logger.info("Scheduled market refresh at 19:30 IST")

        # Start the scheduler
        self.scheduler.start()
        self._started = True
        logger.info("EOD Scheduler started successfully")

    async def _run_signal_computation(self) -> None:
        """Run daily signal computation."""
        logger.info("Starting signal computation...")
        try:
            # Get the latest trade date from fact_eod_price
            df = SignalComputer(self.db_url).compute_all_signals()
            logger.info("Signal computation completed: %s rows computed", len(df))
        except Exception as e:
            logger.error("Signal computation failed: %s", e)
            raise

    async def _run_alert_evaluation(self) -> None:
        """Run daily alert evaluation."""
        logger.info("Starting alert evaluation...")
        try:
            from analytics.alert_engine import run_daily_alert_evaluation

            alerts = await run_daily_alert_evaluation()
            fired_count = sum(1 for a in alerts if a["alert_id"] is not None)
            logger.info("Alert evaluation completed: %d alerts fired", fired_count)

            for alert in alerts:
                if alert["alert_id"]:
                    logger.info("  - %s for %s: %s", alert["alert_name"], alert["symbol"], alert["description"])
        except Exception as e:
            logger.error("Alert evaluation failed: %s", e)
            raise

    async def _run_market_refresh(self) -> None:
        """Run market overview refresh."""
        logger.info("Starting market refresh...")
        try:
            # Refresh any cached market data if needed
            logger.info("Market refresh completed")
        except Exception as e:
            logger.error("Market refresh failed: %s", e)

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if self.scheduler and self._started:
            self.scheduler.shutdown()
            self._started = False
            logger.info("EOD Scheduler stopped")

    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._started


def main() -> None:
    """Entry point for running the scheduler."""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    scheduler = EODScheduler()

    if len(sys.argv) > 1 and sys.argv[1] == "run":
        # Run once immediately (for testing)
        print("Running EOD jobs once...")
        import asyncio

        asyncio.run(scheduler._run_signal_computation())
        asyncio.run(scheduler._run_alert_evaluation())
    else:
        print("Starting EOD Scheduler...")
        print("Press Ctrl+C to stop")
        try:
            scheduler.start()
            # Keep running
            from time import sleep
            while True:
                sleep(60)
        except KeyboardInterrupt:
            print("\nStopping scheduler...")
            scheduler.stop()


if __name__ == "__main__":
    main()
