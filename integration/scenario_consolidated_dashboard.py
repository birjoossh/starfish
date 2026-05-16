"""Integration smoke test for the consolidated single-page dashboard.

Verifies that ``dashboard/app.py``:
    1. Boots through Streamlit's ``AppTest`` without raising
    2. Renders all 8 section headers (§01–§08)
    3. Stays clean when the underlying DB returns no signal data
    4. Stays clean when the underlying DB returns a populated frame

Run from project root:

    source venv/bin/activate
    pytest integration/scenario_consolidated_dashboard.py -v

Note on mocking: ``AppTest.from_file().run()`` ``exec``'s the script in the
``dashboard.app`` module namespace, which re-binds top-level names — so
``unittest.mock.patch('dashboard.app._load_signals', ...)`` only holds for
the *first* call (the import of the module). To intercept calls inside the
running script we patch at the data source instead — ``config.database
.read_sql_df`` and ``dashboard.watchlist.load_watchlist`` — which are
re-resolved on every call via the lazy ``from config.database import …``
pattern in the dashboard modules.
"""
from __future__ import annotations

import datetime as dt
import html
from typing import Iterable
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


APP_PATH = "dashboard/app.py"
DEFAULT_TIMEOUT = 30


@pytest.fixture(autouse=True)
def _clear_streamlit_caches():
    """Clear ``@st.cache_data`` between tests so each starts from a fresh slate.

    Without this, the first test's call to ``_get_available_dates`` caches a
    value (often today's date) that subsequent tests inherit, defeating the
    per-test ``read_sql_df`` mock.
    """
    import streamlit as st  # local import keeps top-level dependency optional
    st.cache_data.clear()
    yield
    st.cache_data.clear()

# Markers expected in the rendered DOM for each section header. The
# section_header primitive emits ``§ NN`` followed by the small-caps title.
EXPECTED_SECTIONS = [
    ("01", "Market Overview"),
    ("02", "Watchlist"),
    ("03", "Trend Workbench"),
    ("04", "Movers & Extremes"),
    ("05", "Drawdown Scanner"),
    ("06", "Breakout & Momentum Monitor"),
    ("07", "Volume Anomaly Monitor"),
    ("08", "Corporate Events Tracker"),
]


# --------------------------- Test fixtures ------------------------------ #


def _fake_signals_frame() -> pd.DataFrame:
    """Build a minimal populated mart_stock_signals frame."""
    today = dt.date.today().isoformat()
    rows = []
    sectors = ["Banks", "IT", "Pharma", "Energy", "Auto"]
    for i in range(10):
        rows.append({
            "calc_date": today,
            "symbol": f"SYM{i:02d}",
            "company_name": f"Company {i}",
            "sector": sectors[i % len(sectors)],
            "market_cap_cr": 50000.0 + i * 1000,
            "close": 1000.0 + i * 10,
            "return_1d": (i - 5) * 0.005,
            "return_1m": (i - 5) * 0.02,
            "return_3m": (i - 5) * 0.04,
            "return_1y": (i - 5) * 0.10,
            "vol_ratio_1d": 1.0 + (i % 3) * 0.4,
            "vol_ratio_5d": 1.0 + (i % 4) * 0.3,
            "vol_ratio_20d": 1.0,
            "avg_volume_20d": 1_000_000 + i * 50_000,
            "volume_trend_3m": ["Stable", "Expanding", "Contracting"][i % 3],
            "drawdown_from_52w_high_pct": -5.0 - i * 2,
            "distance_from_52w_low_pct": 20.0 + i,
            "signal_category": ["Momentum", "Contrarian", "EventDriven", "Neutral"][i % 4],
            "momentum_flag": i % 3 == 0,
            "accumulation_flag": i % 4 == 0,
            "event_flag": i % 5 == 0,
            "iss_score": 30 + i * 5,
            "rs_vs_nifty_3m": (i - 5) * 0.01,
            "rs_vs_nifty_1y": (i - 5) * 0.02,
            "last_event_type": None,
            "days_since_last_event": None,
        })
    return pd.DataFrame(rows)


def _assert_no_runtime_errors(at: AppTest) -> None:
    """Assert the run produced no exceptions or errors."""
    assert not list(at.exception), f"Streamlit raised: {[e.value for e in at.exception]}"
    assert not list(at.error), f"Streamlit error elements: {[e.value for e in at.error]}"


def _collect_markdown_text(at: AppTest) -> str:
    """Concatenate every markdown payload for substring search."""
    return "\n".join(getattr(m, "value", "") or "" for m in at.markdown)


def _assert_all_sections_present(at: AppTest) -> None:
    """Every section header (§ NN + title) must appear in the rendered markdown.

    The ``render_section_header`` primitive HTML-escapes its inputs, so titles
    containing ``&`` end up as ``&amp;``. We search against both the raw blob
    and an unescaped variant.
    """
    raw_blob = _collect_markdown_text(at)
    unescaped_blob = html.unescape(raw_blob)
    missing: list[str] = []
    for num, title in EXPECTED_SECTIONS:
        section_marker = f"§ {num}"
        title_present = title in unescaped_blob or html.escape(title) in raw_blob
        if section_marker not in raw_blob or not title_present:
            missing.append(f"§{num} · {title}")
    assert not missing, f"Section headers not rendered: {missing}"


# ------------------------------- Tests ---------------------------------- #


def _mock_db_distinct_dates(dates: list[str]) -> pd.DataFrame:
    """Build a DataFrame matching the ``SELECT DISTINCT calc_date`` query shape."""
    return pd.DataFrame({"calc_date": [pd.to_datetime(d).date() for d in dates]})


def _read_sql_router(
    *,
    dates: list[str] | None,
    signals: pd.DataFrame,
):
    """Return a ``read_sql_df`` stand-in that routes queries to the right fake.

    AppTest re-runs the dashboard inside its own exec sandbox, so we must
    patch at the data-source seam — ``config.database.read_sql_df`` — which
    is imported lazily inside each consumer.
    """
    def _route(query: str, params: dict | None = None) -> pd.DataFrame:
        low = (query or "").lower()
        if "distinct calc_date" in low:
            return _mock_db_distinct_dates(dates or [dt.date.today().isoformat()])
        if "mart_stock_signals" in low:
            return signals.copy()
        if "fact_eod_price" in low or "fact_corporate_event" in low:
            return pd.DataFrame()
        return pd.DataFrame()
    return _route


def test_empty_data_boot() -> None:
    """Page must render all 8 section headers even with zero signal rows."""
    with patch(
        "config.database.read_sql_df",
        side_effect=_read_sql_router(dates=None, signals=pd.DataFrame()),
    ), patch("dashboard.watchlist.load_watchlist", return_value=set()):
        at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
        at.run()
        _assert_no_runtime_errors(at)
        _assert_all_sections_present(at)


def test_populated_data_boot() -> None:
    """Page must render cleanly with a populated mart_stock_signals frame."""
    fake = _fake_signals_frame()
    with patch(
        "config.database.read_sql_df",
        side_effect=_read_sql_router(dates=None, signals=fake),
    ), patch("dashboard.watchlist.load_watchlist", return_value={"SYM00", "SYM03"}):
        at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
        at.run()
        _assert_no_runtime_errors(at)
        _assert_all_sections_present(at)


def test_scrubber_lands_on_most_recent_date() -> None:
    """Date scrubber must seed ``calc_date`` to the most-recent trading day.

    Regression guard against ``select_slider`` defaulting to its median when
    pre-set ``session_state`` is not honoured (caught in advisor review).
    """
    dates = ["2026-05-09", "2026-05-08", "2026-05-07"]
    with patch(
        "config.database.read_sql_df",
        side_effect=_read_sql_router(dates=dates, signals=pd.DataFrame()),
    ), patch("dashboard.watchlist.load_watchlist", return_value=set()):
        at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
        at.run()
        _assert_no_runtime_errors(at)
        assert at.session_state["calc_date"] == "2026-05-09", (
            f"scrubber landed on {at.session_state['calc_date']!r} not the "
            "most-recent date 2026-05-09"
        )


def test_expand_all_flag_present() -> None:
    """expand_all flag should be initialized to True after first render."""
    with patch(
        "config.database.read_sql_df",
        side_effect=_read_sql_router(dates=None, signals=pd.DataFrame()),
    ), patch("dashboard.watchlist.load_watchlist", return_value=set()):
        at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
        at.run()
        _assert_no_runtime_errors(at)
        assert at.session_state["expand_all"] is True


def test_kpi_strip_renders_live_nifty_index() -> None:
    """TODO-130: §01 KPI cards #1 and #4 must show live values when the
    `/market-overview` payload contains a populated `nifty_index` block.

    The API isn't running under AppTest, so the production code path falls
    through to the empty fallback in ``fetch_market_overview``. This test
    patches the fetcher directly so the new KPI renderers actually execute,
    which is the only way py-only tests can exercise the HTML interpolation
    in ``_nifty_index_kpi`` and ``_vol_20d_kpi``.
    """
    fake = _fake_signals_frame()
    fake_payload = {
        "sector_breadth": [
            {"sector": "Banks", "num_stocks": 2, "advancing": 1, "declining": 1,
             "avg_return_1d": 0.001, "avg_return_1m": 0.02, "avg_iss": 55.0},
        ],
        "components": fake.to_dict("records"),
        "nifty_index": {
            "trade_date": "2026-05-08",
            "close": 24176.15,
            "prev_close": 24326.65,
            "return_1d": -0.0061866,
            "realized_vol_20d": 0.1345,
            "window_days": 38,
        },
    }
    with patch(
        "config.database.read_sql_df",
        side_effect=_read_sql_router(dates=None, signals=fake),
    ), patch("dashboard.watchlist.load_watchlist", return_value=set()), \
         patch("dashboard.overview.fetch_market_overview", return_value=fake_payload):
        at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
        at.run()
        _assert_no_runtime_errors(at)
        blob = _collect_markdown_text(at)
        # Card #1 — live close + 1D delta
        assert "24,176.15" in blob, "card #1 should render the live Nifty close"
        assert "-0.62%" in blob, "card #1 should render the 1D delta"
        # Card #2 — muted bracket pending; new hint must NOT reference TODO-106
        assert "52-Week Bracket" in blob
        assert "TODO-106" not in blob, (
            "TODO-130 regression: stale TODO-106 hint resurfaced in §01"
        )
        assert "have 38" in blob, "card #2 hint should disclose the actual window size"
        # Card #4 — live realized vol
        assert "13.5%" in blob, "card #4 should render the live realized 20D vol"


def test_kpi_strip_pending_when_nifty_index_block_empty() -> None:
    """Out-of-window calc_dates → fallback to muted pending KPIs without
    referencing closed TODO-106. Guards against regressions where the
    rendering helpers KeyError on a missing dict key.
    """
    fake = _fake_signals_frame()
    fake_payload = {
        "sector_breadth": [
            {"sector": "Banks", "num_stocks": 1, "advancing": 0, "declining": 1,
             "avg_return_1d": -0.001, "avg_return_1m": -0.01, "avg_iss": 35.0},
        ],
        "components": fake.to_dict("records"),
        "nifty_index": {
            "trade_date": None,
            "close": None,
            "prev_close": None,
            "return_1d": None,
            "realized_vol_20d": None,
            "window_days": 0,
        },
    }
    with patch(
        "config.database.read_sql_df",
        side_effect=_read_sql_router(dates=None, signals=fake),
    ), patch("dashboard.watchlist.load_watchlist", return_value=set()), \
         patch("dashboard.overview.fetch_market_overview", return_value=fake_payload):
        at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
        at.run()
        _assert_no_runtime_errors(at)
        blob = _collect_markdown_text(at)
        assert "TODO-106" not in blob, (
            "TODO-130 regression: stale TODO-106 hint resurfaced in §01"
        )
        assert "have 0" in blob, "pending hint should disclose window_days=0"


def test_trend_rs_pill_no_stale_todo_reference() -> None:
    """TODO-130: §03 filter-row legend must not advertise RS as unavailable
    by default — the warn pill is now scoped to the stats sidebar and only
    when ``payload.rs_vs_nifty_series`` is None.
    """
    fake = _fake_signals_frame()
    with patch(
        "config.database.read_sql_df",
        side_effect=_read_sql_router(dates=None, signals=fake),
    ), patch("dashboard.watchlist.load_watchlist", return_value=set()):
        at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
        at.run()
        _assert_no_runtime_errors(at)
        blob = _collect_markdown_text(at)
        # Filter row legend was the stale callout — it should no longer be there.
        assert "RS · Nifty unavailable" not in blob, (
            "TODO-130 regression: stale 'RS · Nifty unavailable' pill in §03 legend"
        )
        # §08 header should not reference closed corporate-events TODOs.
        assert "TODO-119/120" not in blob, (
            "TODO-130 regression: stale 'TODO-119/120' hint in §08 header"
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
