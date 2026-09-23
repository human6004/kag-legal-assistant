import json
import sys
from types import SimpleNamespace
from unittest.mock import patch

from benchmark.evaluator.models import parse_system_outputs
from benchmark.runners.common import load_questions, main, run_question
from benchmark.runners.hybridrag_runner import adapt_contexts as hybrid_contexts
from benchmark.runners.kag_runner import adapt_contexts as kag_contexts
from benchmark.runners.nativerag_runner import adapt_contexts as native_contexts


def test_input_isolation_and_output_contract(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps([{
        "id": "T1", "question": "Câu hỏi?", "gold_evidence": "SECRET",
        "gold_markers": "SECRET", "answerable": True, "notes": "SECRET",
    }]), encoding="utf-8")
    assert load_questions(path) == [("T1", "Câu hỏi?")]
    received = []
    def query(question):
        received.append(question)
        return "Theo Điều 8 Nghị định 13/2023/NĐ-CP.", native_contexts([{
            "content": "văn bản", "metadata": {"doc_code": "13/2023/NĐ-CP", "article": "Điều 8"}
        }])
    output = run_question(*load_questions(path)[0], "nativerag", query)
    assert received == ["Câu hỏi?"]
    loaded = parse_system_outputs([output])[0]
    assert loaded.system == "nativerag" and loaded.retrieved_contexts[0].rank == 1
    assert loaded.citations[0].document_id == "13/2023/NĐ-CP"
    assert output["citations"] != output["retrieved_contexts"]
    assert output["error"] is None and output["latency_ms"] >= 0


def test_adapters_missing_metadata_and_failure():
    assert native_contexts([{"content": "x"}])[0] == {
        "rank": 1, "document_id": None, "article": None,
        "clause": None, "point": None, "text": "x", "score": None,
    }
    node = SimpleNamespace(metadata={}, get_content=lambda: "x")
    assert hybrid_contexts([SimpleNamespace(node=node, score=None)])[0]["document_id"] is None
    reporter = SimpleNamespace(report_record=["a"], report_stream_data={
        "a": {"segment": "reference", "content": SimpleNamespace(chunk_datas=[
            SimpleNamespace(content="x", title="", properties={}, score=None)
        ])}
    })
    assert kag_contexts(reporter)[0]["article"] is None
    failure = run_question("T2", "câu hỏi", "kag", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    assert failure["answer"] is None and failure["error"] == "RuntimeError: offline"
    assert failure["citations"] == []
    assert parse_system_outputs([failure])[0].failed


def test_kag_contexts_keep_retrieval_order_without_duplicate_chunks_or_guessed_metadata():
    first = SimpleNamespace(chunk_id="chunk-1", content="Điều 8 Nghị định 13/2023/NĐ-CP", title="",
                            properties={}, score=0.8)
    second = SimpleNamespace(chunk_id="chunk-2", content="Nội dung thứ hai", title="",
                             properties={"article_no": 9}, score=0.5)
    reporter = SimpleNamespace(report_record=["a", "other", "b", "a"], report_stream_data={
        "a": {"segment": "reference", "content": SimpleNamespace(chunks=[first])},
        "other": {"segment": "generator_reference", "content": [second]},
        "b": {"segment": "reference", "content": SimpleNamespace(chunks=[first, second])},
    })
    contexts = kag_contexts(reporter)
    assert [(c["rank"], c["text"], c["document_id"], c["article"]) for c in contexts] == [
        (1, first.content, None, None), (2, second.content, None, "9")]


def test_batch_cli_with_synthetic_question(tmp_path):
    dataset, out = tmp_path / "dataset.json", tmp_path / "output.json"
    dataset.write_text(json.dumps([{"id": "T3", "question": "Synthetic", "gold_claims": "SECRET"}]))
    with patch.object(sys, "argv", ["runner", "--dataset", str(dataset), "--out", str(out)]):
        main("hybridrag", lambda: lambda question: ("No citation", hybrid_contexts([
            SimpleNamespace(node=SimpleNamespace(metadata={"article": 8}, get_content=lambda: question), score=0.2),
            SimpleNamespace(node=SimpleNamespace(metadata={}, get_content=lambda: question), score=None),
        ])))
    outputs = json.loads(out.read_text(encoding="utf-8"))
    assert len(outputs) == 1 and outputs[0]["system"] == "hybridrag"
    assert [c["rank"] for c in outputs[0]["retrieved_contexts"]] == [1, 2]
    assert outputs[0]["retrieved_contexts"][0]["article"] == "8"
    assert outputs[0]["citations"] == []
    assert parse_system_outputs(outputs)[0].question_id == "T3"
