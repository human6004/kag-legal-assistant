# -*- coding: utf-8 -*-
"""Kiểm 5 lỗi của KAG 0.8.0 mà repo này tự vá bằng lớp con.

Chạy (đứng ở thư mục gốc repo):
    .venv/Scripts/python.exe -X utf8 tests/builder/test_builder_fixes.py

Không gọi LLM hay ghi graph; đọc schema từ OpenSPG khi dựng runner.
Các assertion kiểm bản vá project trên KAG đang cài, không xác minh toàn bộ thư viện.

Test nằm ngoài thư mục builder được runtime quét. Cần config local và server
đã đăng ký schema để dựng runner; không gọi runner.invoke.
"""

if __name__ == "__main__":
    import os
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[2]
    os.chdir(ROOT / "kag")
    sys.path.insert(0, str(ROOT / "kag"))

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
    #
    #    Triple hợp lệ ở đây phải là tuple có trong hợp đồng quan hệ B3. Bản cũ
    #    dùng (Others, "quy định", Others) và chờ 1 cạnh: đó là behavior TRƯỚC
    #    B3, nay vị ngữ tự do bị loại đúng theo hợp đồng. Ý định của test không
    #    đổi — "tuple wrapper + triple rác không làm mất triple hợp lệ" — chỉ
    #    đổi mẫu triple hợp lệ sang (Article, imposes, Sanction).
    #    Gọi trực tiếp nên endpoint_ids=None: id cuối đi qua canon_id, không cần
    #    bản đồ danh tính B2 ở tầng thấp này.
    triples = [
        ["Điều 9", "imposes", "Phạt tiền"],
        None,
        ["thiếu", "bộ ba"],
        ["c", 1, "d"],
    ]
    ents = [
        {"name": "Điều 9", "category": "Article"},
        {"name": "Phạt tiền", "category": "Sanction"},
    ]
    graph = ext.assemble_sub_graph_with_triples(SubGraph([], []), ents, (triples,))
    assert len(graph.edges) == 1, [(e.from_id, e.label, e.to_id) for e in graph.edges]
    assert graph.edges[0].label == "imposes", graph.edges[0].label
    print("triple bọc tuple / triple rác     : OK")

    # 4. Một node hỏng chỉ được bỏ chunk đó, không ném lên cho future.
    def boom(*a, **kw):
        raise RuntimeError("gateway chết")

    safe = type(chain)._skip_on_error(boom, "extractor")
    assert safe("chunk") == [], "node hỏng phải trả rỗng chứ không ném"
    print("node hỏng không kéo cả văn bản    : OK")

    # 5. Mỗi thực thể chỉ được một id. KAG ghi mỗi thực thể hai lần vào cùng một
    #    subgraph — một lần tên thô (:302, :312), một lần processing_phrases
    #    (:424) — nên trước bản vá có hai node: node thô giữ quan hệ, node kia
    #    rỗng. Đo trên đồ thị thử 121 chunk: Obligation 419 node cho 169 thực thể.
    g = SubGraph([], [])
    for ten in [
        "Nghị định 329/2026/NĐ-CP",
        "nghị định 329 2026 nđ cp",
        "Nghị định số 329/2026/NĐ-CP",
        "nghị định số 329 2026 nđ cp",
    ]:
        g.add_node(ten, ten, "LegalDocument")
    assert len(g.nodes) == 1, [n.id for n in g.nodes]

    # tên văn bản của metadata và của OpenIE phải về cùng một id
    assert g.nodes[0].id == "nghị định 329 2026 nđ cp", g.nodes[0].id
    print("bốn tên văn bản về một node      : OK")

    # Node nào ghi trước thì giữ tên (sub_graph.py:189-193 không cập nhật name khi
    # trùng id). Đây là thứ quyết định thứ tự injection so với indexer:
    # _named_entity_recognition_process (schema_free_extractor.py:119-150) xử lý
    # external_graph.ner TRƯỚC, tức tên chuẩn từ nodes.json vào danh sách trước
    # tên do mô hình viết. Nên tên chuẩn thắng dù injection chạy trước hay sau.
    g5 = SubGraph([], [])
    g5.add_node("Nghị định 329/2026/NĐ-CP", "Nghị định 329/2026/NĐ-CP", "LegalDocument")
    g5.add_node("Nghị định số 329/2026/NĐ-CP", "Nghị định số 329/2026/NĐ-CP", "LegalDocument")
    assert len(g5.nodes) == 1, [n.id for n in g5.nodes]
    assert g5.nodes[0].name == "Nghị định 329/2026/NĐ-CP", g5.nodes[0].name
    print("tên chuẩn thắng tên mô hình viết : OK")

    g2 = SubGraph([], [])
    for ten in [
        "Bảo vệ dữ liệu cá nhân, bí mật đời tư, thông tin mật và bí mật kinh doanh",
        "bảo vệ dữ liệu cá nhân  bí mật đời tư  thông tin mật và bí mật kinh doanh",
    ]:
        g2.add_node(ten, ten, "Obligation")
    assert len(g2.nodes) == 1, [n.id for n in g2.nodes]
    print("tên thô và tên slug về một node  : OK")

    # Nhưng số hiệu không đứng sau loại văn bản thì KHÔNG được quy về văn bản,
    # nếu không "Điều 1 Nghị định 329" sẽ đè lên chính nghị định 329.
    g3 = SubGraph([], [])
    g3.add_node("Nghị định 329/2026/NĐ-CP", "Nghị định 329/2026/NĐ-CP", "LegalDocument")
    g3.add_node("Điều 1 Nghị định 329/2026/NĐ-CP", "Điều 1 Nghị định 329/2026/NĐ-CP", "Article")
    assert len(g3.nodes) == 2, [n.id for n in g3.nodes]
    print("Điều không gộp vào văn bản       : OK")

    # Chunk giữ nguyên id băm: đổi đi là mất liên hệ với chỉ mục vector.
    cid = "b2c8d28bd04779084f49c52e10e635dd2a3c1586de6fa234a9a3fc8a6e2218ba#4950#table#0#LEN"
    g4 = SubGraph([], [])
    g4.add_node(cid, "tên chunk", "Chunk")
    assert g4.nodes[0].id == cid, g4.nodes[0].id
    print("chunk giữ nguyên id băm          : OK")

    print("\nTất cả đều đúng với KAG gốc, không cần sửa thư viện.")
