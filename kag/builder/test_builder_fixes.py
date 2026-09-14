# -*- coding: utf-8 -*-
"""Kiểm 4 lỗi của KAG 0.8.0 mà repo này tự vá bằng lớp con.

Chạy (đứng ở thư mục gốc repo):
    cd kag; ..\\.venv\\Scripts\\python.exe builder\\test_builder_fixes.py

Không gọi LLM, không đụng Neo4j. Chạy được nghĩa là bản KAG đang cài chưa bị
sửa tay mà dự án vẫn đúng.

Mọi thứ nằm trong __main__ vì indexer.py gọi import_modules_from_path lên cả
thư mục này — assert ở mức module sẽ chạy mỗi lần dựng đồ thị.
"""

if __name__ == "__main__":
    import os

    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from kag.common.conf import init_env, KAG_CONFIG
    from kag.common.registry import import_modules_from_path

    init_env(config_file="kag_config.yaml")
    import_modules_from_path(os.path.join(os.getcwd(), "builder"))

    from kag.builder.runner import BuilderChainRunner
    from kag.builder.model.sub_graph import SubGraph

    runner = BuilderChainRunner.from_config(
        KAG_CONFIG.all_config["kag_builder_pipeline"]
    )
    chain = runner.chain
    ext = chain.extractor

    # Tên lớp phải là bản của repo, không phải bản gốc của KAG. Sai chỗ này
    # nghĩa là kag_config.yaml còn trỏ vào type cũ.
    assert type(chain).__name__ == "LegalUnstructuredBuilderChain", type(chain)
    assert type(ext).__name__ == "LegalSchemaFreeExtractor", type(ext)
    print("chain + extractor đúng lớp        : OK")

    # 1. LLM bọc mảng trong object, và phần tử thiếu "category".
    out = ext._named_entity_recognition_process(
        "x", {"entities": [{"name": "Nghị định 15"}, "rác", {"noname": 1}]}
    )
    assert out == [{"name": "Nghị định 15", "category": "Others"}], out
    print("NER trả dict / thiếu category     : OK")

    # 2. LLM lỗi -> invoke(with_except=False) trả None. Phải ném để tenacity
    #    gọi lại, nuốt là mất thực thể im lặng.
    try:
        ext._named_entity_recognition_process("x", None)
        raise AssertionError("ner_result=None phải ném ValueError")
    except ValueError:
        print("NER trả None ném ValueError       : OK")

    # 3. Dấu phẩy thừa trong _invoke của KAG biến list triple thành tuple
    #    1 phần tử -> mất sạch quan hệ. Kèm triple rác do LLM sinh.
    triples = [["a", "quy định", "b"], None, ["thiếu", "bộ ba"], ["c", 1, "d"]]
    ents = [{"name": "a", "category": "Others"}, {"name": "b", "category": "Others"}]
    graph = ext.assemble_sub_graph_with_triples(SubGraph([], []), ents, (triples,))
    assert len(graph.edges) == 1, [(e.from_id, e.label, e.to_id) for e in graph.edges]
    print("triple bọc tuple / triple rác     : OK")

    # 4. Một node hỏng chỉ được bỏ chunk đó, không ném lên cho future.
    def boom(*a, **kw):
        raise RuntimeError("gateway chết")

    safe = type(chain)._skip_on_error(boom, "extractor")
    assert safe("chunk") == [], "node hỏng phải trả rỗng chứ không ném"
    print("node hỏng không kéo cả văn bản    : OK")

    print("\nTất cả đều đúng với KAG gốc, không cần sửa thư viện.")
