# -*- coding: utf-8 -*-
"""Prompt lập kế hoạch logic form, bản tiếng Việt miền pháp luật.

Thay cho default_lf_static_planning của KAG. Khác bốn file prompt còn lại: file này
KHÔNG chép lại template, chỉ KẾ THỪA RetrieverLFStaticPlanningPrompt và đè đúng hai
thuộc tính lớp là default_case_en / default_case_zh.

LÝ DO KẾ THỪA: __init__ của lớp gốc (lf_static_planning_prompt.py:144-176) tự lắp
template = instruct_en + default_case_en + output_format + tips. Đè default_case_en là
đủ để thay ví dụ mà không đụng vào ngữ pháp logic form. CẤM sửa/chép instruct_zh,
instruct_en, output_format, tips; CẤM override parse_steps / _parse_lf / parse_response /
template_variables / is_json_format. Đầu ra của prompt này bị parse bằng regex rồi dựng
thành GetSPONode/MathNode/DeduceNode/GetNode (dòng 211-304); sai một dấu là planner chết
bằng exception, không phải trả lời sai.

Tên type và quan hệ trong ví dụ lấy từ kag/schema/Legal.schema. Luật bất di bất dịch:
quan hệ phải được khai ĐÚNG TRÊN TYPE CỦA s. Ví dụ `imposes` chỉ có trên Article, không
có trên LegalDocument — dạy planner cạnh không tồn tại thì bước đó tra rỗng. _self_check_cases()
ở cuối file đọc thẳng Legal.schema để tự bắt loại lỗi này.

Bộ 5 case dạy đủ bốn toán tử mà kag_config.yaml đang bật:
  Retrieval (kg_hybrid_executor), Math (py_code_based_math_executor),
  Deduce (kag_deduce_executor), Output (kag_output_executor).

AI GỌI
  kag/solver/planner/lf_kag_static_planner.py ("lf_kag_static_planner") qua
  plan_prompt. LLM invoke truyền {"query": ..., "executors": [...]}, template gốc chỉ
  khai biến $query.

PHẢI SỬA TAY kag_config.yaml: khoá này khai tên THẲNG trong yaml
(kag_solver_pipeline.planner.plan_prompt.type) nên biz_scene KHÔNG với tới:
  default_lf_static_planning  ->  legal_lf_static_planning
"""

import re
from pathlib import Path

from kag.interface import PromptABC
from kag.solver.prompt.lf_static_planning_prompt import (
    RetrieverLFStaticPlanningPrompt,
)

# Khuôn mỗi case giữ y hệt bản gốc (lf_static_planning_prompt.py:117-142): dict đúng hai
# khoá {"query", "answer"}, answer là chuỗi dẫn dắt bằng lời rồi "StepN:..." và
# "ActionN:Toán tử(...)" nằm trong khối ```, mỗi Step đúng một Action. Không phải case nào
# cũng kết bằng output — bản gốc cũng vậy.
DEFAULT_CASE_EN = [
    # --- Retrieval đơn: tra nội dung một điều khoản -------------------------------
    {
        "query": "Điều 26 Luật An ninh mạng 2018 quy định gì?",
        "answer": "Trước tiên cần tra nội dung Điều 26 của Luật An ninh mạng 2018\n```\nStep1:Điều 26 Luật An ninh mạng 2018 quy định gì?\nAction1:Retrieval(s=s1:Article[`Điều 26`], p=p1:belongsTo, o=o1:LegalDocument[`Luật An ninh mạng 2018`])\n```\nSau đó xuất nội dung tra được\n```\nStep2:Xuất kết quả ở Step1\nAction2:output(o1)\n```",
    },
    # --- Retrieval hai bước: hiệu lực của văn bản thay thế -------------------------
    {
        "query": "Luật An ninh mạng 2018 đã bị thay thế bởi văn bản nào?",
        "answer": "Trước tiên cần xác định văn bản thay thế Luật An ninh mạng 2018\n```\nStep1:Luật An ninh mạng 2018 bị thay thế bởi văn bản nào?\nAction1:Retrieval(s=s1:LegalDocument[`Luật An ninh mạng 2018`], p=p1:supersededBy, o=o1:LegalDocument)\n```\nSau đó kiểm tra văn bản thay thế đó đã có hiệu lực hay chưa\n```\nStep2:Ngày có hiệu lực của văn bản tìm được ở Step1 là ngày nào?\nAction2:Retrieval(s=o1, p=p2:dateEffective, o=o2)\n```",
    },
    # --- Bắc cầu qua Article mới tới Sanction (LegalDocument KHÔNG có cạnh imposes) -
    {
        "query": "Nghị định hướng dẫn thi hành Luật An ninh mạng quy định mức phạt bao nhiêu?",
        "answer": "Trước tiên cần tìm nghị định hướng dẫn thi hành Luật An ninh mạng\n```\nStep1:Nghị định nào hướng dẫn thi hành Luật An ninh mạng?\nAction1:Retrieval(s=s1:LegalDocument[`Nghị định`], p=p1:implementsDoc, o=o1:LegalDocument[`Luật An ninh mạng`])\n```\nTiếp theo lấy các điều của nghị định đó, vì chế tài nằm trên Điều chứ không nằm trên văn bản\n```\nStep2:Nghị định tìm được ở Step1 gồm những điều nào?\nAction2:Retrieval(s=s2:Article, p=p2:belongsTo, o=o1)\n```\nSau đó tra các mức phạt mà những điều đó quy định\n```\nStep3:Các điều tìm được ở Step2 quy định những mức phạt nào?\nAction3:Retrieval(s=s2, p=p3:imposes, o=o3:Sanction)\n```\nCuối cùng xuất kết quả\n```\nStep4:Xuất kết quả ở Step3\nAction4:output(o3)\n```",
    },
    # --- Math: so sánh mốc thời gian ---------------------------------------------
    {
        "query": "Nghị định 53/2022/NĐ-CP và Nghị định 13/2023/NĐ-CP, văn bản nào ban hành sau?",
        "answer": "Trước tiên lấy ngày ban hành của Nghị định 53/2022/NĐ-CP\n```\nStep1:Nghị định 53/2022/NĐ-CP ban hành ngày nào?\nAction1:Retrieval(s=s1:LegalDocument[`Nghị định 53/2022/NĐ-CP`], p=p1:dateIssued, o=o1)\n```\nLấy ngày ban hành của Nghị định 13/2023/NĐ-CP\n```\nStep2:Nghị định 13/2023/NĐ-CP ban hành ngày nào?\nAction2:Retrieval(s=s2:LegalDocument[`Nghị định 13/2023/NĐ-CP`], p=p2:dateIssued, o=o2)\n```\nSo sánh hai mốc thời gian để biết văn bản nào ban hành sau\n```\nStep3:So sánh ngày ban hành của hai nghị định\nAction3:Math(content=[`o1`,`o2`], target=`Văn bản nào ban hành sau?`)->math3\n```",
    },
    # --- Deduce: câu hỏi đúng/sai, op=judgement ----------------------------------
    {
        "query": "Doanh nghiệp nước ngoài cung cấp dịch vụ trên mạng Internet có bắt buộc phải xác thực thông tin người dùng không?",
        "answer": "Trước tiên cần tra điều khoản quy định về xác thực thông tin người dùng\n```\nStep1:Điều khoản nào quy định việc xác thực thông tin người dùng?\nAction1:Retrieval(s=s1:Article[`Điều 26`], p=p1:belongsTo, o=o1:LegalDocument[`Luật An ninh mạng 2018`])\n```\nSau đó suy luận xem nghĩa vụ đó có bắt buộc với doanh nghiệp nước ngoài hay không\n```\nStep2:Doanh nghiệp nước ngoài có bắt buộc phải xác thực thông tin người dùng không?\nAction2:Deduce(op=judgement, content=[`o1`], target=`Doanh nghiệp nước ngoài cung cấp dịch vụ trên mạng Internet có bắt buộc phải xác thực thông tin người dùng không?`)->deduce2\n```\nCuối cùng xuất kết quả suy luận\n```\nStep3:Xuất kết quả ở Step2\nAction3:output(deduce2)\n```",
    },
]


@PromptABC.register("legal_lf_static_planning")
class LegalLFStaticPlanningPrompt(RetrieverLFStaticPlanningPrompt):
    # Chỉ hai thuộc tính này. Mọi thứ khác (instruct_en, instruct_zh, output_format, tips,
    # parse_steps, _parse_lf, parse_response, template_variables, is_json_format) giữ
    # nguyên của lớp gốc.
    default_case_en = DEFAULT_CASE_EN
    # cùng một bộ ví dụ cho cả hai ngôn ngữ, để project.language đổi cũng không đổi kết quả
    default_case_zh = DEFAULT_CASE_EN


# ---------------------------------------------------------------------------------
# Tự kiểm. Không import kag.builder.metadata_to_graph: kag/builder/__init__.py có
# monkeypatch chạy lúc import và kéo theo cả stack KAG. Chép lại đúng 6 dòng regex của
# schema_props / schema_rels trong file đó (metadata_to_graph.py:70-89).
# ---------------------------------------------------------------------------------
SCHEMA_FILE = Path(__file__).resolve().parents[2] / "schema" / "Legal.schema"

DEDUCE_OPS = {"judgement", "entailment", "extract", "choice", "multiChoice"}

_ACTION_RE = re.compile(r"^Action\d+:(.*)$", re.MULTILINE)


def _schema_blocks():
    text = SCHEMA_FILE.read_text(encoding="utf-8")
    return re.split(r"^(?=\S)", text, flags=re.M)


def schema_props(label):
    """Thuộc tính của một type, đọc thẳng Legal.schema."""
    for block in _schema_blocks():
        if block.startswith(f"{label}("):
            return set(re.findall(r"^\s{8}(\w+)\(", block, re.M))
    return set()


def schema_rels(label):
    """Quan hệ của một type, đọc thẳng Legal.schema."""
    for block in _schema_blocks():
        if block.startswith(f"{label}("):
            tail = block.split("relations:", 1)
            if len(tail) == 1:
                return set()
            return set(re.findall(r"^\s{8}(\w+)\(", tail[1], re.M))
    return set()


def _schema_rel_targets(label):
    """quan hệ -> tên type ở phía đối diện (dòng `supersededBy(BiThayTheBoi): LegalDocument`)."""
    for block in _schema_blocks():
        if block.startswith(f"{label}("):
            tail = block.split("relations:", 1)
            if len(tail) == 1:
                return {}
            return dict(re.findall(r"^\s{8}(\w+)\([^)]*\):\s*(\w+)", tail[1], re.M))
    return {}


def _predicates(label):
    """p hợp lệ khi tra từ type `label`: quan hệ ∪ thuộc tính (bản gốc cũng dùng thuộc
    tính ở vị trí p, ví dụ p1:FoundationYear / p1:ReleaseTime)."""
    return schema_rels(label) | schema_props(label)


def _parse_retrieval(arg):
    """Bóc (s_alias, s_type, p_name, p_alias, o_alias, o_type) của một Retrieval(...).

    Trả None nếu không phải Retrieval. `s_type`/`o_type` là None khi tham số chỉ là alias
    tham chiếu (dạng `s=o1`) chứ không khai type tại chỗ. Alias trả về KHÔNG kèm
    `:Type[...]`, để dùng trực tiếp làm khoá tra bảng alias.
    """
    m = re.match(r"^Retrieval\((.*)\)$", arg.strip())
    if not m:
        return None
    raw = m.group(1)

    def field(name):
        # `,` bên trong giá trị (target=`A, B`) không bị nhầm là ranh giới tham số vì
        # tham số luôn có dạng `X=` với X là s/p/o.
        mm = re.search(rf"(?:^|,)\s*{name}\s*=\s*([^,]*?)\s*(?=,\s*[spo]\s*=|$)", raw)
        return mm.group(1) if mm else None

    def split_expr(expr):
        if expr is None:
            return None, None
        mm = re.match(r"^([spo]\d+)\s*:\s*([A-Za-z_]\w*)", expr)
        if mm:
            return mm.group(1), mm.group(2)
        mm = re.match(r"^([a-z]+\d+)", expr)
        if mm:
            return mm.group(1), None
        return None, None

    s_expr = field("s")
    o_expr = field("o")
    p_expr = field("p") or ""
    # trả về ALIAS (không phải cả biểu thức `o1:LegalDocument`) làm khoá tra alias_type
    s_alias, s_type = split_expr(s_expr)
    o_alias, o_type = split_expr(o_expr)
    p_alias, p_name = split_expr(p_expr)
    return s_alias, s_type, p_name, p_alias, o_alias, o_type


def _self_check_cases():
    """Kiểm khuôn ví dụ + kiểm ngữ nghĩa logic form đối chiếu Legal.schema.

    Bắt được: khuôn Step/Action, toán tử lạ, alias chưa khai, và QUAN HỆ GẮN SAI TYPE
    (ví dụ LegalDocument -imposes-> Sanction, cạnh không tồn tại trong schema).
    """
    assert len(DEFAULT_CASE_EN) == 5, f"phải đúng 5 case, đang có {len(DEFAULT_CASE_EN)}"

    operators_used = set()
    for case in DEFAULT_CASE_EN:
        assert set(case.keys()) == {"query", "answer"}, f"khuôn case sai: {case.keys()}"
        assert case["query"].strip(), "query rỗng"
        answer = case["answer"]
        steps = re.findall(r"^Step\d+:(.*)$", answer, flags=re.MULTILINE)
        actions = re.findall(r"^Action\d+:(.*)$", answer, flags=re.MULTILINE)
        assert len(steps) == len(actions) > 0, f"Step/Action lệch: {case['query']}"
        assert answer.count("```") == len(steps) * 2, "thiếu khối ``` bao quanh"

        # alias -> type, khai dần theo từng bước
        alias_type = {}
        for action in actions:
            head = re.match(r"^([A-Za-z]+)\(", action.strip())
            assert head, f"toán tử sai định dạng: {action}"
            operator = head.group(1)
            assert operator in ("Retrieval", "Math", "Deduce", "output", "Output"), (
                f"toán tử lạ: {action}"
            )
            operators_used.add(operator)

            if operator == "Retrieval":
                parsed = _parse_retrieval(action)
                assert parsed, f"không bóc được Retrieval: {action}"
                s_expr, s_type, p_name, p_alias, o_expr, o_type = parsed

                assert s_expr, f"thiếu s: {action}"
                assert p_name, f"thiếu tên p sau dấu hai chấm: {action}"

                # s là alias tham chiếu -> lần ngược ra type đã khai ở bước trước. Nếu lúc
                # khai không kèm `:Type` thì lấy type đích của chính quan hệ đã sinh ra nó
                # (schema: `supersededBy(BiThayTheBoi): LegalDocument`), vì alias không type
                # vẫn phải bám vào một quan hệ đã kiểm.
                if s_type is None:
                    assert s_expr in alias_type, (
                        f"alias s chưa từng được khai type: {s_expr} trong {action}"
                    )
                    s_type = alias_type[s_expr]
                assert s_type, (
                    f"không suy ra được type của s={s_expr} trong {action}"
                )

                allowed = _predicates(s_type)
                assert allowed, (
                    f"type {s_type} không có trong {SCHEMA_FILE.name}: {action}"
                )
                assert p_name in allowed, (
                    f"quan hệ '{p_name}' KHÔNG hợp lệ trên type '{s_type}'.\n"
                    f"    action   : {action}\n"
                    f"    quan hệ   : {sorted(schema_rels(s_type))}\n"
                    f"    thuộc tính: {sorted(schema_props(s_type))}"
                )

                # ghi nhớ alias -> type: s lấy type đang kiểm, o lấy type khai tại chỗ hoặc
                # type đích của p trong schema nếu chỉ ghi `o=o1` (bản gốc vẫn viết vậy)
                rel_targets = _schema_rel_targets(s_type)
                alias_type[s_expr] = s_type
                if o_expr:
                    alias_type[o_expr] = o_type or rel_targets.get(p_name)
            elif operator == "Deduce":
                op = re.search(r"op=(\w+)", action)
                assert op, f"Deduce thiếu op=: {action}"
                assert op.group(1) in DEDUCE_OPS, (
                    f"op lạ: {op.group(1)} (hợp lệ: {sorted(DEDUCE_OPS)})"
                )
            if operator == "Math":
                assert "target=`" in action, f"Math thiếu target: {action}"

        # mọi alias được tham chiếu ở bước sau phải đã khai trước đó
        for idx, action in enumerate(actions):
            for alias in re.findall(r"s=\s*([so]\d+)(?!:)", action):
                declared = set()
                for prev in actions[:idx]:
                    declared |= set(re.findall(r"[spo]=([spo]\d+)(?!:)", prev))
                    declared |= set(re.findall(r"[spo]=([spo]\d+):", prev))
                assert alias in declared, f"tham chiếu biến chưa khai: {alias}"

    assert "Math" in operators_used, "bộ case phải có ít nhất một case dùng Math"
    assert "Deduce" in operators_used, "bộ case phải có ít nhất một case dùng Deduce"
    assert "Retrieval" in operators_used and "output" in {
        o.lower() for o in operators_used
    }, "bộ case phải có Retrieval và output"


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    _self_check_cases()
    assert LegalLFStaticPlanningPrompt.default_case_zh is DEFAULT_CASE_EN
    assert (
        LegalLFStaticPlanningPrompt.default_case_en is DEFAULT_CASE_EN
    ), "default_case_en phải là bộ ví dụ tiếng Việt"
    print(
        "[self-check ok] legal_lf_static_planning: "
        f"{len(DEFAULT_CASE_EN)} case, Step/Action khớp khuôn, "
        "mọi quan hệ đối chiếu Legal.schema, có cả Math và Deduce"
    )
