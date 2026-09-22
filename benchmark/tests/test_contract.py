# -*- coding: utf-8 -*-
"""The data contract must refuse anything that ties gold truth to one system.

`gold_chunks.json` / `gold_chunks_hep.json` in the KAG solver key their ground
truth on `chunk_id` values produced by KAG's own `LengthSplitter`. Those files
stay where they are; what must never happen is a *common* benchmark accepting
that shape, because then HybridRAG and NativeRAG would be scored against KAG's
chunking decisions. These tests pin the refusal.
"""
from __future__ import annotations

import io
import json
import os

import pytest

from benchmark.evaluator.models import (
    FORBIDDEN_DATASET_KEYS,
    BenchmarkItem,
    SchemaError,
    SystemOutput,
    citations_mirror_contexts,
    index_outputs,
    load_benchmark,
    load_system_outputs,
    parse_benchmark,
    parse_system_outputs,
)

from .helpers import DOC, citation, context, evidence, item, output


# -- forbidden identifiers --------------------------------------------------


@pytest.mark.parametrize("key", sorted(FORBIDDEN_DATASET_KEYS))
def test_system_internal_identifiers_are_rejected_on_the_item(key: str) -> None:
    payload = {
        "id": "q1",
        "category": "muc_phat",
        "answerable": True,
        "question": "Mức phạt là bao nhiêu?",
        key: ["0_7"],
    }
    with pytest.raises(SchemaError) as exc:
        BenchmarkItem.from_dict(payload)
    assert key in str(exc.value)


@pytest.mark.parametrize("key", sorted(FORBIDDEN_DATASET_KEYS))
def test_system_internal_identifiers_are_rejected_on_evidence(key: str) -> None:
    payload = {
        "id": "q1",
        "category": "muc_phat",
        "answerable": True,
        "question": "Mức phạt là bao nhiêu?",
        "gold_evidence": [{"document_id": DOC, "article": "53", key: "0_7"}],
    }
    with pytest.raises(SchemaError):
        BenchmarkItem.from_dict(payload)


def test_legacy_kag_gold_shape_cannot_be_loaded_as_common_gold() -> None:
    """The literal shape of `kag/solver/data/gold_chunks.json` must not parse."""
    legacy = {
        "id": "q1",
        "category": "muc_phat",
        "answerable": True,
        "question": "Mức phạt là bao nhiêu?",
        "gold_chunks": ["0_7", "0_8"],
    }
    with pytest.raises(SchemaError):
        BenchmarkItem.from_dict(legacy)


# -- required fields --------------------------------------------------------


def test_answerable_is_required_and_must_be_boolean() -> None:
    base = {"id": "q1", "category": "c", "question": "q?"}
    with pytest.raises(SchemaError):
        BenchmarkItem.from_dict(base)
    with pytest.raises(SchemaError):
        BenchmarkItem.from_dict(dict(base, answerable="yes"))
    assert BenchmarkItem.from_dict(dict(base, answerable=False)).answerable is False


def test_answerable_false_is_a_first_class_item() -> None:
    it = item(qid="q9", answerable=False, gold_evidence=[])
    assert it.answerable is False
    assert it.gold_evidence == []


def test_missing_document_id_on_evidence_is_refused() -> None:
    with pytest.raises(SchemaError):
        item(gold_evidence=[{"article": "53"}])


def test_evidence_without_text_is_rejected() -> None:
    """Gold text is what lets a system with no article metadata still score."""
    with pytest.raises(SchemaError) as exc:
        item(gold_evidence=[{"document_id": DOC, "article": "53"}])
    assert "text" in str(exc.value)


def test_evidence_with_blank_text_is_rejected() -> None:
    with pytest.raises(SchemaError):
        item(gold_evidence=[{"document_id": DOC, "article": "53", "text": "   "}])


def test_placeholder_markers_are_dropped() -> None:
    it = item(gold_markers=["<điền đáp án>", "100.000.000 đồng"])
    assert it.gold_markers == ["100.000.000 đồng"]


def test_optional_provenance_fields_are_kept() -> None:
    it = item(
        source_url="https://example.invalid/330-2026",
        source_name="Cổng thông tin giả lập",
        notes="dữ liệu tổng hợp cho unit test",
        verification_status="unverified",
    )
    assert it.source_url == "https://example.invalid/330-2026"
    assert it.source_name == "Cổng thông tin giả lập"
    assert it.notes == "dữ liệu tổng hợp cho unit test"
    assert it.verification_status == "unverified"


def test_unknown_fields_land_in_extra_instead_of_being_lost() -> None:
    it = item(reviewer="nobody")
    assert it.extra["reviewer"] == "nobody"


# -- required vs optional evidence ------------------------------------------


def test_required_evidence_filters_optional_entries() -> None:
    it = item(
        gold_evidence=[
            evidence(article="53", evidence_id="E1"),
            evidence(article="54", evidence_id="E2", required=False),
        ]
    )
    assert [e.evidence_id for e in it.gold_evidence] == ["E1", "E2"]
    assert [e.evidence_id for e in it.required_evidence] == ["E1"]


# -- system output ----------------------------------------------------------


def test_contexts_are_sorted_by_rank_and_rank_is_one_based() -> None:
    out = output(contexts=[context(3, "c3"), context(1, "c1"), context(2, "c2")])
    assert [c.rank for c in out.retrieved_contexts] == [1, 2, 3]
    assert [c.text for c in out.top_k(2)] == ["c1", "c2"]
    with pytest.raises(SchemaError):
        output(contexts=[context(0, "bad")])


def test_rank_defaults_to_list_position_when_absent() -> None:
    out = SystemOutput.from_dict(
        {
            "question_id": "q1",
            "system": "nativerag",
            "retrieved_contexts": [{"text": "a"}, {"text": "b"}],
        }
    )
    assert [c.rank for c in out.retrieved_contexts] == [1, 2]


def test_score_is_optional_and_nullable() -> None:
    out = output(contexts=[context(1, "c1"), context(2, "c2", score=0.31)])
    assert out.retrieved_contexts[0].score is None
    assert out.retrieved_contexts[1].score == pytest.approx(0.31)
    with pytest.raises(SchemaError):
        output(contexts=[{"rank": 1, "score": "high"}])


def test_error_and_latency_round_trip() -> None:
    out = output(error="timeout", latency_ms=12_345)
    assert out.failed is True
    assert out.latency_ms == pytest.approx(12_345.0)
    with pytest.raises(SchemaError):
        output(latency_ms="fast")


# -- citations may not be a copy of the retrieval result --------------------


def test_citations_mirroring_retrieved_contexts_is_detected() -> None:
    """NativeRAG's engine returns its retrieved docs under the name 'citations'."""
    contexts = [
        context(1, "a", article="53"),
        context(2, "b", article="54"),
        context(3, "c", article="55"),
    ]
    copied = output(
        contexts=contexts,
        citations=[citation(article="53"), citation(article="54"), citation(article="55")],
    )
    assert citations_mirror_contexts(copied) is True


def test_citing_a_subset_of_what_was_retrieved_is_not_flagged() -> None:
    contexts = [
        context(1, "a", article="53"),
        context(2, "b", article="54"),
        context(3, "c", article="55"),
    ]
    honest = output(
        contexts=contexts,
        citations=[citation(article="53"), citation(article="54"), citation(article="70")],
    )
    assert citations_mirror_contexts(honest) is False


def test_a_short_citation_list_is_never_flagged() -> None:
    """Two articles retrieved and two articles cited is what a good answer does."""
    out = output(
        contexts=[context(1, "a", article="53"), context(2, "b", article="54")],
        citations=[citation(article="53"), citation(article="54")],
    )
    assert citations_mirror_contexts(out) is False


def test_duplicate_question_ids_are_refused_on_both_sides() -> None:
    with pytest.raises(SchemaError):
        parse_benchmark(
            [
                {"id": "q1", "category": "c", "answerable": True, "question": "a?"},
                {"id": "q1", "category": "c", "answerable": True, "question": "b?"},
            ]
        )
    with pytest.raises(SchemaError):
        index_outputs([output(qid="q1"), output(qid="q1")])


def test_wrapper_objects_are_accepted() -> None:
    items = parse_benchmark(
        {"items": [{"id": "q1", "category": "c", "answerable": True, "question": "a?"}]}
    )
    assert [i.id for i in items] == ["q1"]
    outs = parse_system_outputs({"outputs": [{"question_id": "q1", "system": "kag"}]})
    assert [o.question_id for o in outs] == ["q1"]


def test_round_trip_through_json_files(tmp_path) -> None:
    dataset = [
        {
            "id": "q1",
            "category": "muc_phat",
            "answerable": True,
            "question": "Mức phạt là bao nhiêu?",
            "gold_markers": ["100.000.000 đồng"],
            "gold_claims": ["Mức phạt tiền là 100.000.000 đồng."],
            "gold_evidence": [evidence(article="53", text="Phạt tiền 100.000.000 đồng.")],
        }
    ]
    outputs = [
        {
            "question_id": "q1",
            "system": "hybridrag",
            "answer": "Phạt 100 000 000 đồng.",
            "retrieved_contexts": [context(1, "Phạt tiền 100.000.000 đồng.", article="53")],
            "citations": [citation(article="53")],
            "latency_ms": 900,
            "error": None,
        }
    ]
    ds_path = os.path.join(str(tmp_path), "dataset.json")
    out_path = os.path.join(str(tmp_path), "outputs.json")
    with io.open(ds_path, "w", encoding="utf-8") as fout:
        json.dump(dataset, fout, ensure_ascii=False)
    with io.open(out_path, "w", encoding="utf-8") as fout:
        json.dump(outputs, fout, ensure_ascii=False)

    loaded_items = load_benchmark(ds_path)
    loaded_outputs = load_system_outputs(out_path)
    assert loaded_items[0].gold_evidence[0].norm_article == "53"
    assert loaded_outputs[0].system == "hybridrag"


def test_json_schema_files_exist_and_forbid_the_same_keys() -> None:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("benchmark_schema.json", "system_output_schema.json"):
        path = os.path.join(here, name)
        assert os.path.isfile(path), f"{name} is part of the deliverable"
        with io.open(path, "r", encoding="utf-8") as fin:
            schema = json.load(fin)
        assert schema.get("$schema"), f"{name} must declare its JSON Schema dialect"

    with io.open(os.path.join(here, "benchmark_schema.json"), "r", encoding="utf-8") as fin:
        text = fin.read()
    for key in FORBIDDEN_DATASET_KEYS:
        assert key in text, f"benchmark_schema.json must name {key} as forbidden"


def test_the_json_schema_requires_evidence_text_like_the_loader_does() -> None:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with io.open(os.path.join(here, "benchmark_schema.json"), "r", encoding="utf-8") as fin:
        schema = json.load(fin)
    required = schema["$defs"]["evidenceRef"]["required"]
    assert sorted(required) == ["document_id", "text"]
