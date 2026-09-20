# -*- coding: utf-8 -*-
"""D2.3: kế hoạch không được bịa văn bản, và trả lời một phần không được phủ định sạch.

Chạy offline: chỉ dựng prompt và soi template đã lắp, không LLM, không DB, không
embedding, không Docker. Prompt là thứ duy nhất quyết định hai hành vi này nên
kiểm được ở mức cấu trúc template, giống ``PTestPromptMatchesContract`` của
tests/builder/test_relation_b3.py.

Defect A — REWRITE_DRIFT tại bước static planning. Câu hỏi gốc không nêu văn bản
nào, nhưng planner sinh ra Step mang sẵn "Theo Nghị định 333/2026/NĐ-CP", kéo
retrieval sang văn bản khác trong khi căn cứ đúng nằm ở Luật 116/2025/QH15. Không
có dòng code nào chèn chuỗi đó; nó là LLM tự sinh, vì cả bộ ví dụ few-shot đều có
số hiệu văn bản ngay trong query nên planner học rằng mọi Step phải mang tên một
văn bản. Chặn bằng một case dạy chiều ngược: danh tính văn bản là KẾT QUẢ của
belongsTo, không phải đầu vào của kế hoạch.

Defect B — quy tắc 8 của prompt sinh câu trả lời chỉ có hai nhánh đủ/không đủ, nên
khi căn cứ đúng một phần, mô hình vẫn mở bằng câu phủ định chung rồi tự trích đúng
điều khoản ngay sau đó. Chặn bằng nhánh thứ ba: đủ một phần.

Chạy: rtk proxy .venv/Scripts/python.exe -X utf8 -m unittest tests.solver.test_query_anchor_d23 -v
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kag"))

from solver.prompt.lf_static_planning import (  # noqa: E402
    DEFAULT_CASE_EN,
    LegalLFStaticPlanningPrompt,
    _self_check_cases,
    schema_props,
    schema_rels,
)
from solver.prompt.refer_generator import (  # noqa: E402
    LegalReferGeneratorPrompt,
    TEMPLATE as REFER_TEMPLATE,
)

# Số hiệu văn bản quy phạm Việt Nam: 53/2022/NĐ-CP, 116/2025/QH15, 333/2026/NĐ-CP.
DOC_NUMBER = re.compile(r"\b\d{1,3}/\d{4}/[A-ZĐ\-]+\b")

ABSTAIN = "Không đủ thông tin trong dữ liệu để trả lời."


def steps_of(case):
    return re.findall(r"^Step\d+:(.*)$", case["answer"], flags=re.MULTILINE)


def actions_of(case):
    return re.findall(r"^Action\d+:(.*)$", case["answer"], flags=re.MULTILINE)


def doc_free_cases():
    """Case mà query KHÔNG nêu số hiệu văn bản nào."""
    return [c for c in DEFAULT_CASE_EN if not DOC_NUMBER.search(c["query"])]


class ATestPlannerHasDocFreeCase(unittest.TestCase):
    """Bộ ví dụ phải dạy được tình huống câu hỏi không nêu văn bản."""

    def test_ton_tai_it_nhat_mot_case_query_khong_neu_van_ban(self):
        self.assertTrue(
            doc_free_cases(),
            "mất case query không nêu văn bản: planner quay lại tự bịa số hiệu",
        )

    def test_co_case_tra_nguoc_ra_van_ban_bang_belongsTo(self):
        """Phải có case lấy danh tính văn bản ra bằng belongsTo, không nhận từ query."""
        found = [
            c
            for c in doc_free_cases()
            if any("p=p" in a and ":belongsTo" in a for a in actions_of(c))
        ]
        self.assertTrue(
            found,
            "không case nào dạy tra văn bản bằng belongsTo; danh tính văn bản vẫn là "
            "đầu vào của kế hoạch chứ không phải kết quả retrieval",
        )


class BTestPlannerNeverInjectsDocument(unittest.TestCase):
    """Bất biến cốt lõi của defect A: query không nêu văn bản thì Step cũng không."""

    def test_step_cua_case_khong_neu_van_ban_khong_duoc_mang_so_hieu(self):
        for case in doc_free_cases():
            for step in steps_of(case):
                self.assertIsNone(
                    DOC_NUMBER.search(step),
                    f"query không nêu văn bản nhưng Step lại nêu số hiệu: {step!r} "
                    f"(case: {case['query']!r})",
                )

    def test_action_cua_case_khong_neu_van_ban_khong_duoc_neo_so_hieu(self):
        """Cả tham số `[...]` của Retrieval cũng không được chứa số hiệu văn bản."""
        for case in doc_free_cases():
            for action in actions_of(case):
                self.assertIsNone(
                    DOC_NUMBER.search(action),
                    f"Action neo vào số hiệu văn bản mà query không có: {action!r}",
                )

    def test_khong_hardcode_van_ban_cua_ca_hai_ca_test(self):
        """Sửa phải tổng quát: không được dán 333/2026 hay 116/2025 vào prompt."""
        blob = "\n".join(c["query"] + c["answer"] for c in DEFAULT_CASE_EN)
        for needle in ("333/2026", "116/2025"):
            self.assertNotIn(
                needle,
                blob,
                f"prompt hardcode {needle}: sửa bị overfit vào đúng câu test",
            )


class CTestPlannerCaseStillValid(unittest.TestCase):
    """Case mới không được phá ngữ pháp logic form hay khai quan hệ sai type."""

    def test_self_check_cases_van_pass(self):
        _self_check_cases()

    def test_moi_quan_he_trong_case_moi_ton_tai_dung_tren_type_cua_s(self):
        """Dạy planner một cạnh không có trong schema thì bước đó tra rỗng."""
        for case in doc_free_cases():
            alias_type = {}
            for action in actions_of(case):
                m = re.match(r"^Retrieval\((.*)\)$", action.strip())
                if not m:
                    continue
                raw = m.group(1)
                s = re.search(r"(?:^|,)\s*s\s*=\s*([^,]*?)\s*(?=,\s*[spo]\s*=|$)", raw)
                p = re.search(r"(?:^|,)\s*p\s*=\s*([^,]*?)\s*(?=,\s*[spo]\s*=|$)", raw)
                o = re.search(r"(?:^|,)\s*o\s*=\s*([^,]*?)\s*(?=,\s*[spo]\s*=|$)", raw)
                self.assertTrue(s and p, f"thiếu s hoặc p: {action}")
                s_alias, _, s_type = (s.group(1).partition(":"))
                s_alias = s_alias.strip()
                s_type = s_type.split("[")[0].strip() or alias_type.get(s_alias)
                self.assertTrue(s_type, f"không suy ra được type của s trong {action}")
                p_name = p.group(1).partition(":")[2].strip()
                allowed = schema_rels(s_type) | schema_props(s_type)
                self.assertIn(
                    p_name,
                    allowed,
                    f"quan hệ {p_name!r} không hợp lệ trên type {s_type!r}: {action}",
                )
                alias_type[s_alias] = s_type
                if o:
                    o_alias, _, o_type = o.group(1).partition(":")
                    o_type = o_type.split("[")[0].strip()
                    if o_type:
                        alias_type[o_alias.strip()] = o_type


class DTestPlannerTemplateAssembled(unittest.TestCase):
    """Case chỉ có tác dụng khi lớp gốc thật sự lắp nó vào template."""

    def setUp(self):
        self.template = str(LegalLFStaticPlanningPrompt(language="en").template)

    def test_template_chua_cau_canh_bao_khong_tu_them_van_ban(self):
        self.assertIn("không được tự thêm tên hay số hiệu văn bản", self.template)

    def test_template_chua_action_belongsTo_cua_case_moi(self):
        self.assertIn("p2:belongsTo", self.template)

    def test_template_khong_mat_instruct_va_tips_cua_lop_goc(self):
        """Đè default_case_en thôi; mất instruct/tips là đã chép đè lớp gốc."""
        self.assertIn("Step", self.template)
        self.assertGreater(len(self.template), 4000)


class ETestReferGeneratorHasPartialBranch(unittest.TestCase):
    """Defect B: quy tắc 8 phải có ba nhánh, không phải hai."""

    def test_con_giu_cau_phu_dinh_cho_truong_hop_khong_co_gi(self):
        self.assertIn(ABSTAIN, REFER_TEMPLATE)

    def test_co_nhanh_du_mot_phan(self):
        self.assertIn("một phần", REFER_TEMPLATE)

    def test_cam_mo_dau_bang_cau_phu_dinh_chung_khi_chi_du_mot_phan(self):
        self.assertIn(
            "KHÔNG được mở đầu bằng câu phủ định chung",
            REFER_TEMPLATE,
        )

    def test_trich_duoc_mot_dieu_khoan_diem_thi_khong_phai_khong_du_thong_tin(self):
        """Đúng cái mà Q8 làm sai: trích được điểm g khoản 2 Điều 7 rồi vẫn phủ định."""
        self.assertRegex(
            REFER_TEMPLATE,
            r"điều, khoản, điểm[^.]*một phần, không phải không đủ thông tin",
        )

    def test_cau_phu_dinh_chi_thuoc_nhanh_khong_co_bat_ky_phan_nao(self):
        """Câu phủ định phải nằm sau điều kiện 'không có bất kỳ phần nào'."""
        idx_cond = REFER_TEMPLATE.find("không có bất kỳ phần nào")
        idx_abstain = REFER_TEMPLATE.find(ABSTAIN)
        self.assertNotEqual(idx_cond, -1, "mất điều kiện của nhánh phủ định sạch")
        self.assertNotEqual(idx_abstain, -1)
        self.assertLess(
            idx_cond,
            idx_abstain,
            "câu phủ định không còn gắn với nhánh 'không có bất kỳ phần nào'",
        )

    def test_van_cam_lap_bang_kien_thuc_chung_o_ca_ba_nhanh(self):
        """Nới nhánh một phần không được nới luôn rào chống bịa."""
        self.assertIn("không lấp bằng kiến thức chung", REFER_TEMPLATE)

    def test_template_lap_duoc_va_du_ba_bien(self):
        prompt = LegalReferGeneratorPrompt(language="en")
        self.assertEqual(sorted(prompt.template_variables), ["content", "query", "ref"])
        self.assertIn(ABSTAIN, str(prompt.template))


if __name__ == "__main__":
    unittest.main(verbosity=2)
