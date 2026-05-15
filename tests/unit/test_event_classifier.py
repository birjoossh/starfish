"""Unit tests for ingestion.event_classifier."""

from __future__ import annotations

import pytest

from ingestion.event_classifier import (
    EVENT_EARNINGS,
    EVENT_LARGE_ORDER,
    EVENT_LEADERSHIP,
    EVENT_MA,
    EVENT_OTHER,
    EVENT_PLEDGING,
    EVENT_RATING,
    EVENT_REGULATORY,
    classify_event,
    is_negative_event,
)


class TestEarnings:
    @pytest.mark.parametrize("text", [
        "Audited Financial Results for the quarter ended Dec 31",
        "Q3 Result release",
        "Board meeting to consider results — agenda enclosed",
        "Profit warning issued",
    ])
    def test_routes_to_earnings(self, text):
        assert classify_event(text).event_type == EVENT_EARNINGS

    def test_beat_drives_significance_up(self):
        ce = classify_event("Q3 results — net profit beat consensus by 14%")
        assert ce.event_type == EVENT_EARNINGS
        assert ce.significance == 4

    def test_routine_results_score_two(self):
        ce = classify_event("Audited financial results — quarterly results")
        assert ce.event_type == EVENT_EARNINGS
        assert ce.significance == 2

    def test_profit_warning_is_negative(self):
        ce = classify_event("Profit warning for FY24")
        assert ce.event_type == EVENT_EARNINGS
        assert ce.is_negative is True


class TestLeadershipChange:
    def test_ceo_resignation_is_critical(self):
        ce = classify_event("CEO Mr. X has resigned from the company")
        assert ce.event_type == EVENT_LEADERSHIP
        assert ce.significance == 5
        assert ce.is_negative is True

    def test_md_appointment_is_significant(self):
        ce = classify_event("Appointment of Mr. Y as Managing Director")
        assert ce.event_type == EVENT_LEADERSHIP
        assert ce.significance == 3
        assert ce.is_negative is False

    def test_cfo_step_down_score_three(self):
        ce = classify_event("CFO stepping down, transition effective immediately")
        assert ce.event_type == EVENT_LEADERSHIP
        assert ce.significance == 3

    def test_role_without_action_not_leadership(self):
        # Mentioning "CFO" alone in a conference announcement must not trip
        # the Leadership classifier.
        ce = classify_event("Our CFO will address the investor conference")
        assert ce.event_type != EVENT_LEADERSHIP


class TestMA:
    def test_acquisition_is_critical(self):
        ce = classify_event("Announcement of acquisition of XYZ Pvt Ltd")
        assert ce.event_type == EVENT_MA
        assert ce.significance == 5

    def test_open_offer(self):
        ce = classify_event("Public announcement of open offer")
        assert ce.event_type == EVENT_MA


class TestLargeOrder:
    def test_order_win_routes_correctly(self):
        ce = classify_event("Order received from Ministry of Defence")
        assert ce.event_type == EVENT_LARGE_ORDER
        assert ce.significance == 3

    def test_large_order_score_four(self):
        ce = classify_event("Large order win of substantial value")
        assert ce.event_type == EVENT_LARGE_ORDER
        assert ce.significance == 4


class TestPledging:
    def test_pledge_is_negative_and_high(self):
        ce = classify_event("Disclosure of pledged shares by promoter")
        assert ce.event_type == EVENT_PLEDGING
        assert ce.significance == 4
        assert ce.is_negative is True

    def test_release_of_pledge_not_negative(self):
        ce = classify_event("Release of pledge — 1,00,000 shares")
        assert ce.event_type == EVENT_PLEDGING
        assert ce.is_negative is False


class TestRatingChange:
    def test_downgrade_is_negative_high(self):
        ce = classify_event("ICRA — rating downgrade to AA-")
        assert ce.event_type == EVENT_RATING
        assert ce.significance == 4
        assert ce.is_negative is True

    def test_upgrade_positive_score_three(self):
        ce = classify_event("CRISIL rating action — upgrade to AAA")
        assert ce.event_type == EVENT_RATING
        assert ce.significance == 3
        assert ce.is_negative is False

    def test_outlook_revision_score_three(self):
        ce = classify_event("Outlook revised by S&P Global")
        assert ce.event_type == EVENT_RATING


class TestRegulatory:
    def test_sebi_enforcement_is_critical_negative(self):
        ce = classify_event("SEBI enforcement action — penalty imposed")
        assert ce.event_type == EVENT_REGULATORY
        assert ce.significance == 5
        assert ce.is_negative is True

    def test_court_order_is_high(self):
        ce = classify_event("Supreme court order on tax dispute")
        assert ce.event_type == EVENT_REGULATORY
        assert ce.significance == 4

    def test_show_cause_notice_is_negative(self):
        ce = classify_event("Show cause notice received from RBI")
        assert ce.event_type == EVENT_REGULATORY
        assert ce.is_negative is True


class TestPriorityOrdering:
    def test_rating_outranks_earnings_when_both_present(self):
        # The Rating_Change category sits ahead of Earnings in CATEGORIES,
        # so a results filing that also discloses a rating action is tagged
        # Rating_Change.
        text = "Quarterly results — also disclosing ICRA rating action: downgrade"
        ce = classify_event(text)
        assert ce.event_type == EVENT_RATING


class TestFallback:
    def test_empty_text_is_other(self):
        ce = classify_event("")
        assert ce.event_type == EVENT_OTHER
        assert ce.significance == 1

    def test_none_text_is_other(self):
        ce = classify_event(None)
        assert ce.event_type == EVENT_OTHER

    def test_unrelated_text_is_other_low_significance(self):
        ce = classify_event("Annual general meeting notice")
        # AGM matches the OTHER fallback, not Regulatory
        assert ce.event_type == EVENT_OTHER
        assert ce.significance == 1


class TestIsNegativeHelper:
    def test_pledge_minus_release_is_negative(self):
        assert is_negative_event(EVENT_PLEDGING, "Pledge created") is True
        assert is_negative_event(EVENT_PLEDGING, "Release of pledge") is False

    def test_earnings_miss_is_negative(self):
        assert is_negative_event(EVENT_EARNINGS, "Quarterly results — earnings miss") is True
        assert is_negative_event(EVENT_EARNINGS, "Results meet expectations") is False
