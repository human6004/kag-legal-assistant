import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 1. Create B2_5_CORPUS_CLOSURE.json
closure_items = [
    {
        "id": "Q008",
        "source_id": "C060",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md",
        "verified_location": {
            "article": "3",
            "clause": "4",
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": True,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Hệ thống thông tin quan trọng quốc gia defined in Điều 3 khoản 4 Luật 86/2015/QH13. Exact text match in corpus."
    },
    {
        "id": "Q009",
        "source_id": "C061",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md",
        "verified_location": {
            "article": "3",
            "clause": "11",
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": True,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Phần mềm độc hại defined in Điều 3 khoản 11 Luật 86/2015/QH13. Exact text match in corpus."
    },
    {
        "id": "Q032",
        "source_id": "C062",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md",
        "verified_location": {
            "article": "7",
            "clause": "5",
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": True,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Prohibited acts regarding personal information in Điều 7 khoản 5 Luật 86/2015/QH13. Exact text match in corpus."
    },
    {
        "id": "Q045",
        "source_id": "C147",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_ai/367-QD-TTg_ke-hoach-trien-khai-thi-hanh-luat-tri-tue-nhan-tao.md",
        "verified_location": {
            "article": "3",
            "clause": "3",
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": True,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Drafting regulations implementing AI Law assigned to Bộ Khoa học và Công nghệ with listed legal products under Section II.3 of Kế hoạch ban hành kèm Quyết định 367/QĐ-TTg (referenced via Điều 3). Exact text match in corpus."
    },
    {
        "id": "Q067",
        "source_id": "N009",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md",
        "verified_location": {
            "article": "32",
            "clause": "3",
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": True,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "30 days timeframe for Ban Cơ yếu Chính phủ to evaluate and issue license in Điều 32 khoản 3 Luật 86/2015/QH13. Exact text match in corpus."
    },
    {
        "id": "Q087",
        "source_id": "N014",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md",
        "verified_location": {
            "article": "53",
            "clause": None,
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": None,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Effective date of Luật 86/2015/QH13 (01/07/2016) in Điều 53. Exact text match in corpus."
    },
    {
        "id": "Q092",
        "source_id": "C064",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_an_ninh_mang/35-2018-QH14_sua-doi-37-luat-lien-quan-quy-hoach.md",
        "verified_location": {
            "article": "2",
            "clause": "2",
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": True,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Luật 35/2018/QH14 Điều 2 khoản 2 modifies khoản 12 Điều 12 Bộ luật Hàng hải. Exact text match in corpus."
    },
    {
        "id": "Q093",
        "source_id": "C067",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_an_ninh_mang/35-2018-QH14_sua-doi-37-luat-lien-quan-quy-hoach.md",
        "verified_location": {
            "article": "18",
            "clause": None,
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": None,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Luật 35/2018/QH14 Điều 18 modifies Luật An toàn thông tin mạng 86/2015/QH13. Exact text match in corpus."
    },
    {
        "id": "Q094",
        "source_id": "C068",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_an_ninh_mang/35-2018-QH14_sua-doi-37-luat-lien-quan-quy-hoach.md",
        "verified_location": {
            "article": "8",
            "clause": "4",
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": True,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Luật 35/2018/QH14 Điều 8 khoản 4 modifies Điều 11 Luật Khoáng sản. Exact text match in corpus."
    },
    {
        "id": "Q095",
        "source_id": "C070",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md; data/processed/vn_an_ninh_mang/35-2018-QH14_sua-doi-37-luat-lien-quan-quy-hoach.md",
        "verified_location": {
            "article": "51 (Luật 86), 18 (Luật 35)",
            "clause": "1",
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": True,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Inter-document pair: Điều 51 khoản 1 Luật 86/2015/QH13 and Điều 18 Luật 35/2018/QH14. Both evidence legs confirmed with exact text match in corpus."
    },
    {
        "id": "Q097",
        "source_id": "C086",
        "corpus_status": "CORPUS_REPAIR",
        "corpus_file": "data/processed/vn_an_ninh_mang/356-2025-ND-CP_quy-dinh-chi-tiet-luat-bao-ve-du-lieu-ca-nhan.md",
        "verified_location": {
            "article": "42",
            "clause": "1, 2",
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": True,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Corpus repair applied: expanded gold_evidence to include both Điều 42 khoản 1 (hiệu lực 01/01/2026) and Điều 42 khoản 2 (Nghị định 13 hết hiệu lực); added '01 tháng 01 năm 2026' to gold_markers so that both questions are fully supported by corpus."
    },
    {
        "id": "Q102",
        "source_id": "C146",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_ai/367-QD-TTg_ke-hoach-trien-khai-thi-hanh-luat-tri-tue-nhan-tao.md",
        "verified_location": {
            "article": "3",
            "clause": None,
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": None,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Plan text in Quyết định 367/QĐ-TTg (attached plan under Điều 3) details implementation of Luật Trí tuệ nhân tạo 134/2025/QH15, passing date (10/12/2025), and effective date (01/03/2026). Exact text match in corpus."
    },
    {
        "id": "Q110",
        "source_id": "N025",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_an_ninh_mang/35-2018-QH14_sua-doi-37-luat-lien-quan-quy-hoach.md",
        "verified_location": {
            "article": "27",
            "clause": None,
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": None,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Luật 35/2018/QH14 Điều 27 modifies khoản 2 Điều 4 Luật Quảng cáo. Exact text match in corpus."
    },
    {
        "id": "Q122",
        "source_id": "C065",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md",
        "verified_location": {
            "article": "40, 45",
            "clause": "2, 3",
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": True,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Multi-hop query across Điều 40 khoản 2 (10-year term) and Điều 45 khoản 3 (one extension <= 1 year, submit <= 60 days) of Luật 86/2015/QH13. Both evidence legs confirmed with exact text match in corpus."
    },
    {
        "id": "Q135",
        "source_id": "C148",
        "corpus_status": "CORPUS_READY",
        "corpus_file": "data/processed/vn_ai/367-QD-TTg_ke-hoach-trien-khai-thi-hanh-luat-tri-tue-nhan-tao.md",
        "verified_location": {
            "article": "2, 3",
            "clause": None,
            "point": None
        },
        "checks": {
            "document": True,
            "article": True,
            "clause": None,
            "point": None,
            "evidence": True,
            "question_supported": True,
            "markers_supported": True
        },
        "notes": "Multi-hop query covering Điều 2 (effective upon signature) and Điều 3 (responsibility for execution) of Quyết định 367/QĐ-TTg. Both evidence legs confirmed with exact text match in corpus."
    }
]

with open('benchmark/work/B2_5_CORPUS_CLOSURE.json', 'w', encoding='utf-8') as f:
    json.dump(closure_items, f, ensure_ascii=False, indent=2)
print(f"Created benchmark/work/B2_5_CORPUS_CLOSURE.json ({len(closure_items)} items)")

# 2. Create final_150_corpus_verified.json
with open('benchmark/work/final_150_candidate.json', 'r', encoding='utf-8') as f:
    candidate_data = json.load(f)

verified_data = []
for item in candidate_data:
    item_copy = json.loads(json.dumps(item))  # deep copy
    if item_copy['id'] == 'Q097':
        # Apply repair
        item_copy['gold_evidence'] = [
            {
                "document_id": "356/2025/NĐ-CP",
                "article": "42",
                "clause": "1",
                "point": None,
                "text": "1. Nghị định này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2026."
            },
            {
                "document_id": "356/2025/NĐ-CP",
                "article": "42",
                "clause": "2",
                "point": None,
                "text": "2. Nghị định số 13/2023/NĐ-CP ngày 17 tháng 4 năm 2023 của Chính phủ về bảo vệ dữ liệu cá nhân hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành."
            }
        ]
        item_copy['gold_markers'] = [
            "01 tháng 01 năm 2026",
            "Nghị định số 13/2023/NĐ-CP",
            "hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành"
        ]
        item_copy['notes'] = "Corpus repair: added Điều 42 khoản 1 for effective date (01/01/2026) alongside khoản 2."
    verified_data.append(item_copy)

with open('benchmark/work/final_150_corpus_verified.json', 'w', encoding='utf-8') as f:
    json.dump(verified_data, f, ensure_ascii=False, indent=2)
print(f"Created benchmark/work/final_150_corpus_verified.json ({len(verified_data)} items)")
