# -*- coding: utf-8 -*-
"""Normalization must be tolerant about presentation and strict about meaning.

The legacy KAG `norm_text` stripped every "." and "," globally, which also
destroyed decimals ("30,5%" -> "305%") and document codes. These tests pin down
both halves of the contract: what must become equal, and what must stay apart.
"""
from __future__ import annotations

import pytest

from benchmark.evaluator.normalization import (
    MARKER_PROFILE,
    contains_marker,
    normalize_article,
    normalize_clause,
    normalize_document_id,
    normalize_for_match,
    normalize_point,
    normalize_text,
    token_coverage,
    token_set,
    tokenize,
)


# -- tolerance -------------------------------------------------------------


@pytest.mark.parametrize(
    "a, b",
    [
        # MANDATORY CASE 1: thousand separators are presentation, not meaning.
        ("100.000.000", "100 000 000"),
        ("100.000.000 đồng", "100 000 000 đồng"),
        ("30.000.000", "30,000,000"),
        ("30.000.000", "30 000 000"),
        ("1.500.000.000", "1 500 000 000"),
        # Markdown wrapping is presentation.
        ("**100.000.000 đồng**", "100 000 000 đồng"),
        ("`Điều 53`", "Điều 53"),
        # Case and NFC form are presentation.
        ("ĐIỀU 53", "Điều 53"),
    ],
)
def test_equal_after_normalization(a: str, b: str) -> None:
    assert normalize_text(a) == normalize_text(b)


def test_mandatory_case_1_marker_match() -> None:
    """`100.000.000` in gold must be found in an answer written `100 000 000 đồng`."""
    answer = "Mức phạt tiền là 100 000 000 đồng đối với hành vi này."
    assert contains_marker(answer, "100.000.000") is True


# -- strictness ------------------------------------------------------------


@pytest.mark.parametrize(
    "a, b",
    [
        # Article numbers must never be reordered or merged.
        ("Điều 13", "Điều 31"),
        ("Điều 53", "Điều 52"),
        ("Điều 5", "Điều 50"),
        # Decimals and rates are meaning, not separators.
        ("30,5%", "305%"),
        ("30,5%", "30,6%"),
        ("0,5 lần", "05 lần"),
        # Different amounts stay different.
        ("30.000.000", "3.000.000"),
        # Document numbers must stay apart.
        ("330/2026/NĐ-CP", "331/2026/NĐ-CP"),
        ("330/2026/NĐ-CP", "330/2025/NĐ-CP"),
        # Negation must survive.
        ("không được phép", "được phép"),
        ("chưa có quy định", "có quy định"),
        # Money units are meaning.
        ("30 triệu đồng", "30 tỷ đồng"),
    ],
)
def test_different_after_normalization(a: str, b: str) -> None:
    assert normalize_text(a) != normalize_text(b)


def test_decimal_separator_survives() -> None:
    """A separator inside a decimal is not a thousand separator."""
    assert "," in normalize_text("lãi suất 30,5%/năm")
    assert normalize_text("30,5") == "30,5"


def test_article_number_not_merged_into_neighbour() -> None:
    """`Điều 13` must not be reachable from an answer that only says `Điều 31`."""
    assert contains_marker("Xử phạt theo Điều 31.", "Điều 13") is False


# -- profiles ---------------------------------------------------------------


def test_text_profile_collapses_whitespace_marker_profile_strips_it() -> None:
    assert normalize_text("Điều   53\n\tkhoản 3") == "điều 53 khoản 3"
    assert normalize_for_match("Điều   53\n\tkhoản 3") == "điều53khoản3"


def test_marker_profile_is_the_substring_profile() -> None:
    assert MARKER_PROFILE.strip_whitespace is True
    assert contains_marker("mức phạt 100.000.000 đồng", "100 000 000") is True


def test_empty_marker_never_matches() -> None:
    assert contains_marker("bất kỳ nội dung nào", "") is False
    assert contains_marker("bất kỳ nội dung nào", "   ") is False
    assert contains_marker(None, "100.000.000") is False


# -- tokens -----------------------------------------------------------------


def test_tokenize_keeps_vietnamese_words_and_numbers() -> None:
    assert tokenize("Phạt 30.000.000 đồng") == ["phạt", "30000000", "đồng"]
    assert token_set("a a b") == {"a", "b"}


def test_token_coverage_bounds_and_none() -> None:
    assert token_coverage("phạt tiền", "Mức phạt tiền là 30 triệu") == 1.0
    assert token_coverage("", "bất kỳ") is None, "no tokens to cover -> None, not 0.0"
    assert token_coverage("phạt tiền", None) == 0.0
    coverage = token_coverage("phạt tiền cảnh cáo", "chỉ có phạt tiền")
    assert coverage is not None and 0.0 < coverage < 1.0


# -- structural labels ------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Điều 53", "53"),
        ("điều 53", "53"),
        ("Dieu 53", "53"),
        ("53", "53"),
        ("Article 53.", "53"),
        ("53a", "53a"),
        (None, None),
        ("", None),
    ],
)
def test_normalize_article(raw, expected) -> None:
    assert normalize_article(raw) == expected


def test_article_labels_stay_distinct() -> None:
    assert normalize_article("Điều 13") != normalize_article("Điều 31")


@pytest.mark.parametrize(
    "raw, expected",
    [("khoản 3", "3"), ("Khoan 3", "3"), ("3)", "3"), ("3", "3"), (None, None)],
)
def test_normalize_clause(raw, expected) -> None:
    assert normalize_clause(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [("điểm b", "b"), ("diem b)", "b"), ("b", "b"), ("B", "b"), (None, None)],
)
def test_normalize_point(raw, expected) -> None:
    assert normalize_point(raw) == expected


def test_document_id_forms_converge_but_numbers_do_not() -> None:
    canonical = normalize_document_id("330/2026/NĐ-CP")
    assert canonical == normalize_document_id("330-2026-ND-CP")
    assert canonical == normalize_document_id("Nghị định số 330/2026/NĐ-CP")
    assert canonical == normalize_document_id("  nghi dinh 330/2026/nd-cp  ")
    assert canonical != normalize_document_id("331/2026/NĐ-CP")
    assert canonical != normalize_document_id("330/2025/NĐ-CP")
    assert normalize_document_id(None) is None
    assert normalize_document_id("   ") is None


def test_document_prefix_removal_does_not_eat_the_number() -> None:
    assert normalize_document_id("Luật số 15/2012/QH13") == normalize_document_id(
        "15/2012/QH13"
    )
