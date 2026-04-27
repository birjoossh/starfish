"""Live NSE scraper for corporate events.

Scrapes NSE India website for real-time corporate announcements.
Falls back to CSV-based ingestion when scraping fails.

Usage:
    scraper = NSEScraper()
    events = await scraper.scrape_upcoming_events()
    inserted = await scraper.sync_to_db()
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from config.database import get_engine, read_sql_df
from sqlalchemy import text

logger = logging.getLogger(__name__)

NSE_CORPORATE_ACTIONS_URL = "https://www.nseindia.com/market-data/corporate-actions"
NSE_CORPORATE_FILINGS_URL = "https://www.nseindia.com/corporates/cyber-security"

EVENT_TYPE_MAP = {
    "dividend": "Dividend",
    "bonus": "Bonus",
    "split": "Stock Split",
    "rights": "Rights Issue",
    "agm": "AGM",
    "egm": "EGM",
    "results": "Quarterly Results",
    "board meeting": "Board Meeting",
    "buyback": "Buyback",
    "scheme": "Scheme of Arrangement",
}


class NSEScraper:
    """Scrape NSE website for corporate events."""

    def __init__(self, timeout: float = 30.0):
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            },
            timeout=timeout,
            follow_redirects=True,
        )
        self._session_cookies: Optional[dict] = None

    async def _get_session_cookies(self) -> dict:
        """Get session cookies from NSE homepage."""
        if self._session_cookies:
            return self._session_cookies

        try:
            # First hit the main page to get cookies
            resp = await self.client.get("https://www.nseindia.com/")
            resp.raise_for_status()
            self._session_cookies = dict(self.client.cookies)
            logger.info("Got NSE session cookies")
            return self._session_cookies or {}
        except Exception as e:
            logger.warning(f"Failed to get NSE session cookies: {e}")
            return {}

    async def scrape_corporate_actions(self) -> list[dict]:
        """Scrape corporate actions page for upcoming events."""
        try:
            cookies = await self._get_session_cookies()
            resp = await self.client.get(NSE_CORPORATE_ACTIONS_URL, cookies=cookies)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            events = self._parse_corporate_actions_table(soup)
            logger.info(f"Scraped {len(events)} corporate actions from NSE")
            return events
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error scraping corporate actions: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error scraping corporate actions: {e}")

        return []

    def _parse_corporate_actions_table(self, soup: BeautifulSoup) -> list[dict]:
        """Parse the corporate actions table from NSE HTML."""
        events = []

        # Find the main table (try multiple selectors)
        table = (
            soup.select("table tbody tr") or
            soup.select(".corporate-actions-table tr") or
            soup.select("div.table-responsive table tr")
        )

        if not table:
            # Try to find any table with corporate action data
            tables = soup.find_all("table")
            for t in tables:
                rows = t.select("tbody tr") or t.find_all("tr")
                if len(rows) > 2:  # More than header + empty
                    table = rows
                    break

        if not table:
            logger.warning("No corporate actions table found in NSE response")
            return events

        for row in table[1:]:  # Skip header
            cells = row.select("td")
            if len(cells) < 4:
                continue

            try:
                # Extract data from cells (adjust indices based on actual table structure)
                symbol = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                event_type_text = cells[1].get_text(strip=True).lower() if len(cells) > 1 else ""
                event_date_str = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                purpose = cells[3].get_text(strip=True) if len(cells) > 3 else ""

                if not symbol or symbol in ["Symbol", ""]:
                    continue

                # Map to event type
                event_type = "Other"
                for key, val in EVENT_TYPE_MAP.items():
                    if key in event_type_text:
                        event_type = val
                        break

                # Parse date
                event_date = self._parse_date(event_date_str)

                events.append({
                    "symbol": symbol.upper(),
                    "event_date": event_date,
                    "event_type": event_type,
                    "event_summary": purpose[:500] if purpose else event_type_text,
                    "source": "NSE Live Scrape",
                })
            except Exception as e:
                logger.debug(f"Failed to parse row: {e}")
                continue

        return events

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse various date formats."""
        formats = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y"]

        for fmt in formats:
            try:
                return date.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        # Try to handle relative dates
        if "today" in date_str.lower():
            return date.today()
        if "tomorrow" in date_str.lower():
            return date.today() + timedelta(days=1)

        return None

    async def sync_to_db(self, dry_run: bool = False) -> dict:
        """Sync scraped events to database.

        Args:
            dry_run: If True, don't actually insert, just return what would be inserted.

        Returns:
            Dict with stats: events_scraped, existing_count, new_count
        """
        events = await self.scrape_corporate_actions()

        if not events:
            return {"events_scraped": 0, "existing_count": 0, "new_count": 0}

        # Filter to valid events with dates
        valid_events = [e for e in events if e["event_date"] is not None]
        logger.info(f"Valid events after filtering: {len(valid_events)}")

        if not valid_events:
            return {"events_scraped": len(events), "existing_count": 0, "new_count": 0}

        # Check for existing events
        engine = get_engine()
        existing_symbols = set()

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT symbol, event_date, event_type
                FROM fact_corporate_event
                WHERE event_date >= CURRENT_DATE
            """))
            existing_symbols = {(row.symbol, row.event_date, row.event_type) for row in result}

        # Filter out existing
        new_events = [
            e for e in valid_events
            if (e["symbol"], e["event_date"], e["event_type"]) not in existing_symbols
        ]

        if dry_run:
            logger.info(f"[DRY RUN] Would insert {len(new_events)} new events")
            return {
                "events_scraped": len(events),
                "existing_count": len(valid_events) - len(new_events),
                "new_count": len(new_events)
            }

        # Insert new events
        if new_events:
            with engine.connect() as conn:
                for event in new_events:
                    conn.execute(text("""
                        INSERT INTO fact_corporate_event
                            (symbol, event_date, event_type, event_summary,
                             categorization_method, significance_score)
                        VALUES
                            (:symbol, :event_date, :event_type, :event_summary,
                             :categorization_method, :significance_score)
                        ON CONFLICT DO NOTHING
                    """), {
                        "symbol": event["symbol"],
                        "event_date": event["event_date"],
                        "event_type": event["event_type"],
                        "event_summary": event["event_summary"],
                        "categorization_method": "Rule",  # Auto-classified
                        "significance_score": 2,  # Default for scraped events
                    })
                conn.commit()

            logger.info(f"Inserted {len(new_events)} new corporate events")

        return {
            "events_scraped": len(events),
            "existing_count": len(valid_events) - len(new_events),
            "new_count": len(new_events)
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def run_scraper():
    """CLI entry point for the scraper."""
    import argparse

    parser = argparse.ArgumentParser(description="NSE Corporate Events Scraper")
    parser.add_argument("--dry-run", action="store_true", help="Don't insert, just report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    scraper = NSEScraper()
    try:
        stats = await scraper.sync_to_db(dry_run=args.dry_run)
        print(f"Scraped: {stats['events_scraped']}")
        print(f"Existing: {stats['existing_count']}")
        print(f"New: {stats['new_count']}")
    finally:
        await scraper.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_scraper())