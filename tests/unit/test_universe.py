"""Unit tests for services.universe.membership_covers (pure logic)."""

from __future__ import annotations

from datetime import date

import pytest

from services.universe import membership_covers


def _interval(eff_from, eff_to, change_type="Addition"):
    return (eff_from, eff_to, change_type)


class TestSingleInterval:
    def test_inside_open_interval(self):
        intervals = [_interval(date(2020, 1, 1), None)]
        assert membership_covers(intervals, date(2024, 6, 15)) is True

    def test_inside_closed_interval(self):
        intervals = [_interval(date(2020, 1, 1), date(2023, 12, 31))]
        assert membership_covers(intervals, date(2022, 6, 15)) is True

    def test_before_effective_from(self):
        intervals = [_interval(date(2020, 1, 1), None)]
        assert membership_covers(intervals, date(2019, 12, 31)) is False

    def test_after_effective_to(self):
        intervals = [_interval(date(2020, 1, 1), date(2022, 12, 31))]
        assert membership_covers(intervals, date(2023, 1, 1)) is False

    def test_exactly_on_effective_from(self):
        intervals = [_interval(date(2020, 1, 1), None)]
        assert membership_covers(intervals, date(2020, 1, 1)) is True

    def test_exactly_on_effective_to(self):
        intervals = [_interval(date(2020, 1, 1), date(2022, 12, 31))]
        assert membership_covers(intervals, date(2022, 12, 31)) is True


class TestDeletionRows:
    def test_deletion_row_alone_returns_false(self):
        intervals = [_interval(date(2020, 1, 1), None, "Deletion")]
        assert membership_covers(intervals, date(2024, 6, 15)) is False

    def test_deletion_row_does_not_mask_other_addition(self):
        intervals = [
            _interval(date(2018, 1, 1), date(2020, 12, 31), "Deletion"),
            _interval(date(2022, 1, 1), None, "Addition"),
        ]
        assert membership_covers(intervals, date(2023, 6, 15)) is True


class TestReentry:
    def test_member_then_removed_then_member_again(self):
        intervals = [
            _interval(date(2018, 1, 1), date(2019, 12, 31)),
            _interval(date(2022, 1, 1), None),
        ]
        assert membership_covers(intervals, date(2018, 6, 15)) is True
        assert membership_covers(intervals, date(2020, 6, 15)) is False
        assert membership_covers(intervals, date(2023, 6, 15)) is True


class TestRebalance:
    def test_rebalance_treated_as_membership(self):
        intervals = [_interval(date(2021, 1, 1), None, "Rebalance")]
        assert membership_covers(intervals, date(2024, 6, 15)) is True


class TestEmpty:
    def test_no_intervals_returns_false(self):
        assert membership_covers([], date(2024, 6, 15)) is False
