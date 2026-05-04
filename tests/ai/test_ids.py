"""Unit tests for ai.utils.ids."""

from __future__ import annotations

import pytest

from dbt_builder.src.ai.utils.ids import stable_id, stable_short_id


def test_stable_id_is_deterministic():
    assert stable_id("hub", "ce") == stable_id("hub", "ce")


def test_stable_id_normalises_whitespace_and_case():
    assert stable_id("Hub", "CE") == stable_id(" hub ", "ce")


def test_stable_id_distinguishes_positional_emptiness():
    assert stable_id("a", "") != stable_id("a")


def test_stable_id_treats_none_as_empty_string():
    assert stable_id("a", None) == stable_id("a", "")


def test_stable_id_requires_at_least_one_part():
    with pytest.raises(ValueError):
        stable_id()


def test_stable_id_length_is_40_hex():
    sid = stable_id("anything")
    assert len(sid) == 40
    assert all(c in "0123456789abcdef" for c in sid)


def test_stable_short_id_default_length_is_12():
    assert len(stable_short_id("a")) == 12


def test_stable_short_id_custom_length_within_bounds():
    assert len(stable_short_id("a", length=8)) == 8


@pytest.mark.parametrize("bad", [0, 3, 41, 100])
def test_stable_short_id_rejects_invalid_length(bad: int):
    with pytest.raises(ValueError):
        stable_short_id("a", length=bad)
