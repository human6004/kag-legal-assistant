# -*- coding: utf-8 -*-
"""One parser, three answer styles, one set of citations.

The three systems are prompted to cite in prose, and that is the only channel
they share: KAG also emits `<reference>` tags that index its own trace log, and
NativeRAG's engine hands back its retrieved documents under the name
"citations". If each adapter were allowed to fill `citations[]` its own way,
Citation Recall would measure three different things - and NativeRAG's would be
its retrieval recall, obtained for free.
"""
from __future__ import annotations

from benchmark.adapters.citation_parser import (
    citation_key,
    parse_citation_payloads,
    parse_citations,
)

DOC = "13/2023/NĐ-CP"

# The same legal content, written the way each system's prompt asks for it.
KAG_ANSWER = (
    "Mức phạt tiền là 30.000.000 đồng theo khoản 2 Điều 8 Nghị định 13/2023/NĐ-CP"
    '<reference id="chunk:1_2"></reference>.'
)
HYBRID_ANSWER = (
    "Mức phạt tiền là 30.000.000 đồng (Điều 8 khoản 2 Nghị định 13/2023/NĐ-CP).\n"
    "Căn cứ: Điều 8 khoản 2 Nghị định 13/2023/NĐ-CP"
)
NATIVE_ANSWER = (
    "Theo Điều 8 khoản 2 Nghị định 13/2023/NĐ-CP, mức phạt tiền là 30.000.000 đồng."
)


def keys(answer: str):
    return [citation_key(c) for c in parse_citations(answer)]


# -- the property the contract rests on -------------------------------------


def test_three_answer_styles_produce_the_same_citations() -> None:
    assert keys(KAG_ANSWER) == keys(HYBRID_ANSWER) == keys(NATIVE_ANSWER)
    assert keys(KAG_ANSWER) == [("13/2023/nd/cp", "8", "2", None)]


def test_reference_tags_are_ignored() -> None:
    """A `<reference id="chunk:1_2">` points at a trace log, not at a law."""
    with_tag = 'Điều 8 Nghị định 13/2023/NĐ-CP<reference id="chunk:1_2"></reference>.'
    without = "Điều 8 Nghị định 13/2023/NĐ-CP."
    assert keys(with_tag) == keys(without)
    payloads = parse_citation_payloads(with_tag)
    assert all("chunk" not in str(p) for p in payloads)


# -- the recognised forms ----------------------------------------------------


def test_the_deepest_form_is_parsed_whole() -> None:
    parsed = parse_citations("điểm b khoản 2 Điều 8 Nghị định 13/2023/NĐ-CP")
    assert len(parsed) == 1
    assert (parsed[0].article, parsed[0].clause, parsed[0].point) == ("8", "2", "b")


def test_article_only_and_document_only_forms() -> None:
    assert keys("Điều 8 Nghị định 13/2023/NĐ-CP") == [("13/2023/nd/cp", "8", None, None)]
    assert keys("Quy định tại Nghị định 13/2023/NĐ-CP") == [
        ("13/2023/nd/cp", None, None, None)
    ]


def test_a_law_number_is_recognised_like_a_decree_number() -> None:
    assert keys("Điều 5 Luật 59/2020/QH14") == [("59/2020/qh14", "5", None, None)]


def test_an_answer_that_cites_nothing_yields_nothing() -> None:
    assert parse_citations("Không tìm thấy quy định nào về nội dung này.") == []
    assert parse_citations(None) == []
    assert parse_citations("") == []


# -- the shared rules --------------------------------------------------------


def test_document_is_inherited_from_the_nearest_preceding_mention() -> None:
    answer = (
        "Theo Điều 8 Nghị định 13/2023/NĐ-CP, hành vi bị xử phạt. "
        "Ngoài ra Điều 12 quy định biện pháp khắc phục."
    )
    assert keys(answer) == [
        ("13/2023/nd/cp", "8", None, None),
        ("13/2023/nd/cp", "12", None, None),
    ]


def test_a_later_document_replaces_the_inherited_one() -> None:
    answer = (
        "Điều 8 Nghị định 13/2023/NĐ-CP quy định mức phạt. "
        "Điều 5 Luật 59/2020/QH14 quy định nguyên tắc, còn Điều 6 quy định thẩm quyền."
    )
    assert keys(answer) == [
        ("13/2023/nd/cp", "8", None, None),
        ("59/2020/qh14", "5", None, None),
        ("59/2020/qh14", "6", None, None),
    ]


def test_a_clause_before_any_document_is_dropped_rather_than_invented() -> None:
    assert parse_citations("Theo khoản 2, mức phạt là 30.000.000 đồng.") == []


def test_a_list_of_articles_stays_a_list() -> None:
    assert keys("Điều 8 và Điều 9 Nghị định 13/2023/NĐ-CP") == [
        (None, "8", None, None),
        ("13/2023/nd/cp", "9", None, None),
    ]


def test_repeating_a_citation_neither_helps_nor_hurts() -> None:
    once = "Điều 8 Nghị định 13/2023/NĐ-CP."
    twice = "Điều 8 Nghị định 13/2023/NĐ-CP. Xem lại Điều 8 Nghị định 13/2023/NĐ-CP."
    assert keys(once) == keys(twice)


def test_payloads_match_the_system_output_shape() -> None:
    payloads = parse_citation_payloads("khoản 2 Điều 8 Nghị định 13/2023/NĐ-CP")
    assert payloads == [{"document_id": DOC, "article": "8", "clause": "2"}]
