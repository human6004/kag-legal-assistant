# -*- coding: utf-8 -*-
"""D2.1: giá trị định lượng quy phạm phải đi qua được cổng assemble.

Defect: `80%` (NĐ 333/2026 Điều 28) và `100%` (NĐ 329/2026 Điều 16) có trong
văn bản nguồn nhưng không có node nào trong graph mang chúng.

Biên mất mát ĐO ĐƯỢC, không phải đoán: A/B prompt NER trên chính chunk thật của
splitter cho thấy NER vẫn trích đúng con số ở CẢ hai bản prompt, nhưng gán
``category: "Others"``. `extractor.py` bỏ mọi thực thể có category ngoài
``SEMANTIC_CATEGORIES`` (dòng `if category not in SEMANTIC_CATEGORIES: continue`)
nên node không bao giờ được cấp danh tính. Vậy đây là ENTITY_ASSEMBLY_LOSS do
category, KHÔNG phải NER_LOSS. Đối chứng cùng lô: `Phạt tiền từ 1% đến 2% doanh
thu` được gán Sanction nên có mặt trong graph — cùng một dấu `%`, khác category,
khác kết cục.

Vì vậy phần sửa được là prompt NER: cấm dùng Others cho nhóm định lượng và chỉ
cho phép các category NẰM TRONG cổng. Test này khoá đúng bất biến đó — prompt
không được dạy model một category mà extractor sẽ bỏ. Không kiểm chất lượng LLM
(cần gọi mạng), chỉ kiểm hợp đồng giữa prompt và cổng assemble.

Chạy: rtk proxy .venv/Scripts/python.exe -X utf8 -m unittest tests.builder.test_ner_quantitative_d21 -v
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kag"))

from builder.canon_id import SEMANTIC_CATEGORIES  # noqa: E402

NER_FILE = ROOT / "kag" / "builder" / "prompt" / "ner.py"
EXTRACTOR_FILE = ROOT / "kag" / "builder" / "extractor.py"
SCHEMA_FILE = ROOT / "kag" / "schema" / "Legal.schema"

# Nhãn extractor tự lo danh tính ngoài đường SEMANTIC_CATEGORIES, cộng Others là
# thùng rác cuối cùng của KAG. Prompt được phép nhắc chúng, nhưng KHÔNG được
# hướng nhóm định lượng vào đó.
NGOAI_CONG = frozenset(("Article", "LegalDocument", "Chunk", "Others"))


def _template():
    """Lấy TEMPLATE bằng AST, không import module.

    ner.py import knext.schema.client ở mức module; test này phải chạy được khi
    không có OpenSPG server, nên đọc bằng AST thay vì import.
    """
    tree = ast.parse(NER_FILE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "TEMPLATE":
            return node.value.value
    raise AssertionError("không tìm thấy TEMPLATE trong ner.py")


TEMPLATE = _template()
PROMPT = json.loads(Template(TEMPLATE).safe_substitute(schema="[]", input="x"))
INSTRUCTION = PROMPT["instruction"]


def _rule(so):
    """Thân của quy tắc "(N) ..." trong instruction."""
    m = re.search(rf"\({so}\)(.*?)(?=\(\d+\)|$)", INSTRUCTION, re.S)
    assert m, f"instruction không có quy tắc ({so})"
    return m.group(1)


def _cac_category(doan):
    ten = set(SEMANTIC_CATEGORIES) | NGOAI_CONG
    return {c for c in ten if re.search(rf"\b{c}\b", doan)}


class ATestTemplateConNguyenVen(unittest.TestCase):
    """Sửa instruction là sửa một chuỗi trong JSON: dễ làm hỏng cả prompt."""

    def test_json_hop_le_sau_khi_thay_bien(self):
        self.assertIsInstance(PROMPT, dict)
        self.assertEqual(
            set(PROMPT) & {"instruction", "schema", "example", "input"},
            {"instruction", "schema", "example", "input"},
        )

    def test_quy_tac_danh_so_lien_tuc_khong_trung(self):
        so = re.findall(r"\((\d+)\)", INSTRUCTION)
        self.assertEqual(so, [str(i) for i in range(1, len(so) + 1)], so)
        self.assertGreaterEqual(len(so), 10, "mất quy tắc")

    def test_bien_template_khong_doi(self):
        self.assertIn("$schema", TEMPLATE)
        self.assertIn("$input", TEMPLATE)


class BTestQuyTacDinhLuongConDo(unittest.TestCase):
    """Quy tắc (9) là phần sửa của D2.1; mất nó là defect quay lại."""

    def setUp(self):
        self.r9 = _rule(9)

    def test_co_quy_tac_ve_gia_tri_dinh_luong(self):
        self.assertIn("định lượng", self.r9)

    def test_khong_gioi_han_o_don_vi_tien(self):
        # Trước D2.1 quy tắc mức phạt chỉ nói "giữ nguyên con số và đơn vị tiền",
        # nên đơn vị không phải tiền (%, ngày) bị coi là không cần giữ.
        self.assertNotIn("đơn vị tiền", INSTRUCTION)
        self.assertIn("đơn vị", _rule(2))

    def test_neu_ro_cac_dang_don_vi_khong_phai_tien(self):
        for dang in ("phần trăm", "thời hạn", "số lượng"):
            self.assertIn(dang, self.r9, dang)

    def test_doi_giu_nguyen_con_so(self):
        self.assertRegex(self.r9, r"giữ nguyên con số")

    def test_giu_ca_phan_chi_bac(self):
        # "Mức 1, tối đa bằng 100% mức lương" — mất tiền tố bậc là mất thông tin
        # phân biệt giữa ba mức cùng dạng câu.
        self.assertIn("Mức 1", self.r9)


class CTestPromptKhopCongAssemble(unittest.TestCase):
    """Bất biến gốc: prompt không được dạy category mà extractor sẽ bỏ."""

    def test_cong_assemble_van_la_semantic_categories(self):
        # Nếu extractor đổi cách lọc thì test này phải được viết lại, không
        # được để nó vẫn xanh với một cổng khác.
        src = EXTRACTOR_FILE.read_text(encoding="utf-8")
        self.assertIn("if category not in SEMANTIC_CATEGORIES:", src)

    def test_quy_tac_9_cam_others(self):
        r9 = _rule(9)
        self.assertRegex(r9, r"không dùng Others")

    def test_moi_category_quy_tac_9_neu_deu_qua_cong(self):
        named = _cac_category(_rule(9)) - {"Others"}
        self.assertTrue(named, "quy tắc (9) phải nêu ít nhất một category thay thế")
        ngoai = named - set(SEMANTIC_CATEGORIES)
        self.assertEqual(
            ngoai, set(),
            f"quy tắc (9) hướng vào category extractor sẽ bỏ: {sorted(ngoai)}",
        )

    def test_khong_bia_category_ngoai_schema(self):
        nhan_schema = set(
            re.findall(r"^(\w+)\(", SCHEMA_FILE.read_text(encoding="utf-8"), re.M)
        )
        for cat in _cac_category(INSTRUCTION) - NGOAI_CONG:
            self.assertIn(cat, nhan_schema, f"{cat} không có trong Legal.schema")

    def test_van_con_duong_lui_others_o_quy_tac_cuoi(self):
        # Others vẫn phải là lựa chọn cuối cho thực thể ngoài mọi nhóm, chỉ là
        # không dành cho nhóm định lượng.
        self.assertIn("Others", _rule(10))


class DTestViDuKhongDayCaiSai(unittest.TestCase):
    """example trong prompt có sức nặng hơn lời văn: nó là thứ model bắt chước."""

    def setUp(self):
        self.entities = PROMPT["example"][0]["output"]

    def test_moi_thuc_the_vi_du_du_bon_truong(self):
        for e in self.entities:
            self.assertEqual(set(e), {"name", "type", "category", "description"}, e)

    def test_khong_vi_du_nao_dung_others(self):
        self.assertEqual([e for e in self.entities if e["category"] == "Others"], [])

    def test_thuc_the_mang_con_so_deu_qua_cong(self):
        mang_so = [e for e in self.entities if re.search(r"\d", e["name"])]
        self.assertTrue(mang_so, "ví dụ phải có ít nhất một thực thể mang con số")
        for e in mang_so:
            self.assertIn(
                e["category"], set(SEMANTIC_CATEGORIES) | {"Article"},
                f"ví dụ dạy category bị bỏ: {e['name']} -> {e['category']}",
            )

    def test_vi_du_muc_phat_giu_nguyen_con_so(self):
        sanctions = [e["name"] for e in self.entities if e["category"] == "Sanction"]
        self.assertTrue(any(re.search(r"\d[\d.]*\.000", n) for n in sanctions), sanctions)


if __name__ == "__main__":
    unittest.main(verbosity=2)
