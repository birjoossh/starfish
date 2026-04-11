"""Unit tests for ingestion/purpose_parser.py."""

import pytest
from ingestion.purpose_parser import (
    parse_purpose, event_significance,
    EVENT_DIVIDEND, EVENT_BONUS, EVENT_SPLIT, EVENT_RIGHTS,
    EVENT_BUYBACK, EVENT_AGM, EVENT_EGM, EVENT_RESULTS, EVENT_OTHER,
)


# ─── Dividend ────────────────────────────────────────────────────────────────

class TestDividend:
    def test_basic_dividend(self):
        r = parse_purpose("DIVIDEND - RS 12.50 PER SHARE")
        assert r.event_type == EVENT_DIVIDEND
        assert r.amount == pytest.approx(12.5)

    def test_interim_dividend(self):
        r = parse_purpose("INTERIM DIVIDEND - RS 5 PER SHARE")
        assert r.event_type == EVENT_DIVIDEND
        assert r.amount == pytest.approx(5.0)

    def test_final_dividend(self):
        r = parse_purpose("FINAL DIVIDEND RS 2 PER SHARE")
        assert r.event_type == EVENT_DIVIDEND
        assert r.amount == pytest.approx(2.0)

    def test_dividend_no_amount(self):
        r = parse_purpose("DIVIDEND")
        assert r.event_type == EVENT_DIVIDEND
        assert r.amount is None

    def test_special_dividend(self):
        r = parse_purpose("SPECIAL DIVIDEND - RS 100")
        assert r.event_type == EVENT_DIVIDEND
        assert r.amount == pytest.approx(100.0)


# ─── Bonus ───────────────────────────────────────────────────────────────────

class TestBonus:
    def test_bonus_1_2(self):
        r = parse_purpose("BONUS 1:2")
        assert r.event_type == EVENT_BONUS
        assert r.ratio_num == 1
        assert r.ratio_den == 2

    def test_bonus_3_1(self):
        r = parse_purpose("BONUS 3:1")
        assert r.event_type == EVENT_BONUS
        assert r.ratio_num == 3
        assert r.ratio_den == 1

    def test_bonus_slash_separator(self):
        r = parse_purpose("BONUS 2/5")
        assert r.event_type == EVENT_BONUS
        assert r.ratio_num == 2


# ─── Split ───────────────────────────────────────────────────────────────────

class TestSplit:
    def test_split_with_face_value(self):
        r = parse_purpose("STOCK SPLIT FROM RS 10 TO RS 2")
        assert r.event_type == EVENT_SPLIT
        assert r.ratio_num == 5  # 10/2 = 5x multiplier

    def test_split_no_ratio(self):
        r = parse_purpose("SUBDIVISION OF SHARES")
        assert r.event_type == EVENT_SPLIT

    def test_split_keyword(self):
        r = parse_purpose("SPLIT OF EQUITY SHARES")
        assert r.event_type == EVENT_SPLIT


# ─── Rights ──────────────────────────────────────────────────────────────────

class TestRights:
    def test_rights_3_7(self):
        r = parse_purpose("RIGHTS 3:7 @ RS 450")
        assert r.event_type == EVENT_RIGHTS
        assert r.ratio_num == 3
        assert r.ratio_den == 7

    def test_rights_1_2(self):
        r = parse_purpose("RIGHTS 1:2")
        assert r.event_type == EVENT_RIGHTS


# ─── Buyback ─────────────────────────────────────────────────────────────────

class TestBuyback:
    def test_buyback(self):
        r = parse_purpose("BUY BACK OF SHARES")
        assert r.event_type == EVENT_BUYBACK

    def test_buyback_single_word(self):
        r = parse_purpose("BUYBACK")
        assert r.event_type == EVENT_BUYBACK


# ─── AGM / EGM / Results ─────────────────────────────────────────────────────

class TestMeetings:
    def test_agm(self):
        assert parse_purpose("AGM").event_type == EVENT_AGM

    def test_egm(self):
        assert parse_purpose("EGM").event_type == EVENT_EGM

    def test_results(self):
        assert parse_purpose("QUARTERLY RESULTS").event_type == EVENT_RESULTS

    def test_other(self):
        assert parse_purpose("SOME UNKNOWN CORPORATE ACTION").event_type == EVENT_OTHER


# ─── Significance Scoring ────────────────────────────────────────────────────

class TestSignificance:
    def test_bonus_scores_5(self):
        assert event_significance(parse_purpose("BONUS 1:2")) == 5

    def test_split_scores_5(self):
        assert event_significance(parse_purpose("STOCK SPLIT FROM RS 10 TO RS 2")) == 5

    def test_buyback_scores_5(self):
        assert event_significance(parse_purpose("BUYBACK")) == 5

    def test_rights_scores_4(self):
        assert event_significance(parse_purpose("RIGHTS 3:7")) == 4

    def test_large_dividend_scores_4(self):
        assert event_significance(parse_purpose("DIVIDEND - RS 15 PER SHARE")) == 4

    def test_medium_dividend_scores_3(self):
        assert event_significance(parse_purpose("DIVIDEND - RS 5 PER SHARE")) == 3

    def test_small_dividend_scores_2(self):
        assert event_significance(parse_purpose("DIVIDEND - RS 0.5 PER SHARE")) == 2

    def test_agm_scores_2(self):
        assert event_significance(parse_purpose("AGM")) == 2

    def test_results_scores_3(self):
        assert event_significance(parse_purpose("QUARTERLY RESULTS")) == 3

    def test_other_scores_1(self):
        assert event_significance(parse_purpose("UNKNOWN ACTION")) == 1
