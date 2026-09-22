import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Bộ dữ liệu benchmark chuẩn cho bài toán Trợ lý Pháp lý Việt Nam (An ninh mạng, AI, Dữ liệu cá nhân)
BENCHMARK_DATASET = [
    {
        "case_id": "legal_ai_deepfake_01",
        "user_input": "Dùng AI dựng lại khuôn mặt và giọng nói của người khác để qua bước xác thực tài khoản ngân hàng thì bị phạt bao nhiêu tiền và theo quy định nào?",
        "reference": (
            "Hành vi sử dụng trí tuệ nhân tạo để giả mạo, tái tạo khuôn mặt, giọng nói của người khác nhằm vượt qua xác thực "
            "tài khoản ngân hàng là hành vi vi phạm nghiêm trọng về an ninh mạng và bảo vệ dữ liệu cá nhân. "
            "Theo quy định tại Điều 34 Nghị định xử phạt vi phạm hành chính trong lĩnh vực an ninh mạng (hoặc các quy định liên quan "
            "về mạo danh trên không gian mạng), mức phạt tiền đối với cá nhân thực hiện hành vi này thường từ 30.000.000 đồng đến 50.000.000 đồng, "
            "đồng thời có thể bị truy cứu trách nhiệm hình sự nếu cấu thành tội phạm lừa đảo chiếm đoạt tài sản."
        ),
        "reference_contexts": [
            "Điều 34 quy định xử phạt vi phạm hành chính đối với hành vi sử dụng công nghệ số, trí tuệ nhân tạo để giả mạo hình ảnh, giọng nói, khuôn mặt của cá nhân khác. Mức phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng.",
            "Luật An ninh mạng nghiêm cấm hành vi sử dụng không gian mạng để thực hiện hành vi lừa đảo, chiếm đoạt tài sản hoặc giả mạo trang thông tin, tài khoản của tổ chức, cá nhân khác."
        ],
        "answers": ["30.000.000", "50.000.000", "Điều 34"]
    },
    {
        "case_id": "legal_fake_news_enterprise_02",
        "user_input": "Doanh nghiệp lập nhóm trên mạng xã hội để đăng tải và hướng dẫn phát tán thông tin sai sự thật gây hoang mang trong Nhân dân thì bị phạt tiền bao nhiêu và có bị đình chỉ hoạt động không?",
        "reference": (
            "Căn cứ theo Điều 11 Nghị định quy định về phòng chống và xử phạt vi phạm hành chính về thông tin sai sự thật trên không gian mạng, "
            "tổ chức/doanh nghiệp có hành vi thành lập nhóm hoặc chỉ đạo phát tán thông tin sai sự thật gây hoang mang dư luận bị phạt tiền từ "
            "20.000.000 đồng đến 30.000.000 đồng (đối với cá nhân) hoặc nhân đôi đối với tổ chức. Đồng thời, doanh nghiệp có thể bị áp dụng "
            "hình thức xử phạt bổ sung là đình chỉ hoạt động có thời hạn từ 01 đến 03 tháng và buộc gỡ bỏ thông tin sai sự thật."
        ),
        "reference_contexts": [
            "Điều 11. Xử phạt vi phạm quy định về trách nhiệm sử dụng dịch vụ mạng xã hội và lan truyền thông tin sai lệch. Mức phạt tiền từ 20.000.000 đồng đến 30.000.000 đồng. Hình thức phạt bổ sung: Đình chỉ hoạt động có thời hạn đối với tổ chức vi phạm nhiều lần hoặc có tổ chức.",
            "Nghị định quy định chi tiết biện pháp phòng chống tin giả, tin sai sự thật trên không gian mạng quy định các biện pháp ngăn chặn và chế tài xử lý đối với nhóm quản trị viên và doanh nghiệp vi phạm."
        ],
        "answers": ["20.000.000", "30.000.000", "Điều 11", "đình chỉ hoạt động"]
    },
    {
        "case_id": "legal_pdp_sell_sensitive_03",
        "user_input": "Một công ty mua bán trái phép dữ liệu cá nhân nhạy cảm của 300 người nhưng không thu được khoản tiền nào từ hành vi này thì bị phạt tiền bao nhiêu, quy định tại điều nào?",
        "reference": (
            "Theo quy định tại Điều 53 của Nghị định quy định xử phạt vi phạm hành chính về bảo vệ dữ liệu cá nhân, hành vi mua bán trái phép "
            "dữ liệu cá nhân nhạy cảm (dù chưa thu được lợi nhuận bất hợp pháp) bị phạt tiền từ 100.000.000 đồng đến 300.000.000 đồng. "
            "Ngoài ra, tổ chức vi phạm bị buộc xóa, hủy toàn bộ dữ liệu cá nhân thu thập trái phép."
        ),
        "reference_contexts": [
            "Điều 53. Vi phạm quy định về mua bán, chuyển giao dữ liệu cá nhân trái phép. Hành vi mua bán dữ liệu cá nhân nhạy cảm dưới 1.000 chủ thể dữ liệu mà không có lợi nhuận hoặc chưa xác định được lợi nhuận bị phạt tiền từ 100.000.000 đồng đến 300.000.000 đồng.",
            "Nghị định 13/2023/NĐ-CP và Luật Bảo vệ dữ liệu cá nhân nghiêm cấm tuyệt đối mọi hành vi mua bán dữ liệu cá nhân dưới mọi hình thức."
        ],
        "answers": ["100.000.000", "300.000.000", "Điều 53"]
    },
    {
        "case_id": "legal_ai_high_risk_04",
        "user_input": "Trước khi đưa vào sử dụng, hệ thống trí tuệ nhân tạo có rủi ro cao bắt buộc phải qua thủ tục gì và nhà cung cấp phải thông báo kết quả phân loại cho cơ quan nào?",
        "reference": (
            "Căn cứ theo Điều 13 Luật Trí tuệ nhân tạo và Nghị định hướng dẫn chi tiết, trước khi đưa vào vận hành hoặc lưu thông trên thị trường, "
            "hệ thống AI có rủi ro cao bắt buộc phải trải qua thủ tục 'đánh giá sự phù hợp' (conformity assessment). "
            "Đồng thời, tổ chức/doanh nghiệp phát triển hoặc cung cấp hệ thống AI phải thông báo kết quả phân loại rủi ro cho Bộ Khoa học và Công nghệ "
            "để được thẩm định và quản lý theo quy định."
        ),
        "reference_contexts": [
            "Điều 13. Quản lý hệ thống trí tuệ nhân tạo có rủi ro cao. Hệ thống AI thuộc danh mục rủi ro cao phải được thực hiện đánh giá sự phù hợp trước khi triển khai thực tế. Nhà cung cấp có trách nhiệm gửi thông báo kết quả tự phân loại và hồ sơ kỹ thuật tới Bộ Khoa học và Công nghệ.",
            "Khung đạo đức và quy định chi tiết Luật Trí tuệ nhân tạo nêu rõ yêu cầu về tính minh bạch, an toàn kỹ thuật và trách nhiệm giải trình của hệ thống AI rủi ro cao."
        ],
        "answers": ["đánh giá sự phù hợp", "Bộ Khoa học và Công nghệ", "Điều 13"]
    }
]


def _normalize_sample(raw_item: Dict[str, Any]) -> Dict[str, Any]:
    """Chuẩn hóa linh hoạt các trường khác nhau trong JSON/JSONL về dạng chuẩn."""
    user_input = (
        raw_item.get("user_input")
        or raw_item.get("input")
        or raw_item.get("question")
        or raw_item.get("query")
        or ""
    )

    reference = (
        raw_item.get("reference")
        or raw_item.get("reference_answer")
        or raw_item.get("ground_truth")
        or raw_item.get("target")
        or raw_item.get("answer")
        or ""
    )

    # Nếu answers là một danh sách các từ khóa chuẩn (như trong questions.json của KAG)
    answers = raw_item.get("answers", [])
    if not reference and answers:
        reference = "Các căn cứ và từ khóa bắt buộc gồm: " + ", ".join(answers)

    raw_contexts = (
        raw_item.get("reference_contexts")
        or raw_item.get("contexts")
        or raw_item.get("context")
        or []
    )

    if not raw_contexts and "gold_evidence" in raw_item:
        gold = raw_item["gold_evidence"]
        if isinstance(gold, list):
            raw_contexts = [
                g.get("content", "") if isinstance(g, dict) else str(g)
                for g in gold
            ]

    if isinstance(raw_contexts, str):
        contexts = [raw_contexts]
    elif isinstance(raw_contexts, list):
        contexts = [
            c.get("content", str(c)) if isinstance(c, dict) else str(c)
            for c in raw_contexts
        ]
    else:
        contexts = []

    return {
        "user_input": user_input.strip(),
        "reference": reference.strip(),
        "reference_contexts": contexts,
        "answers": answers,
        "case_id": raw_item.get("case_id", ""),
        "intent_family": raw_item.get("intent_family", raw_item.get("nhom", "")),
        "tags": raw_item.get("tags", []),
        "raw": raw_item
    }


def load_dataset_flexible(file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Nạp bộ dữ liệu đánh giá linh hoạt từ file .jsonl hoặc .json.
    - Ưu tiên file_path truyền vào.
    - Tự động kiểm tra file questions trong thư mục kag/solver/data/questions.json hoặc pilot.jsonl.
    - Mặc định dùng BENCHMARK_DATASET pháp lý.
    """
    target_path = None

    candidate_paths = []
    if file_path:
        candidate_paths.append(Path(file_path))
        candidate_paths.append(PROJECT_ROOT / file_path)
        candidate_paths.append(PROJECT_ROOT / "evaluation" / file_path)

    # Các vị trí mặc định
    candidate_paths.extend([
        PROJECT_ROOT / "pilot.jsonl",
        PROJECT_ROOT.parent / "kag" / "solver" / "data" / "questions.json",
        PROJECT_ROOT.parent / "kag" / "solver" / "data" / "questions_mo_rong.json",
    ])

    for p in candidate_paths:
        if p.exists():
            target_path = p
            break

    if target_path is None:
        print("[DATASET] Sử dụng BENCHMARK_DATASET pháp lý mặc định.")
        return [_normalize_sample(item) for item in BENCHMARK_DATASET]

    print(f"[DATASET] Đang nạp dữ liệu đánh giá từ: {target_path}")
    samples = []

    if target_path.suffix.lower() == ".jsonl":
        with open(target_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    samples.append(_normalize_sample(item))
                except json.JSONDecodeError as err:
                    print(f"[CẢNH BÁO] Lỗi cú pháp JSON dòng {line_no}: {err}")

    elif target_path.suffix.lower() == ".json":
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    samples.append(_normalize_sample(item))
            elif isinstance(data, dict):
                list_data = data.get("data") or data.get("samples") or [data]
                for item in list_data:
                    samples.append(_normalize_sample(item))

    print(f"[DATASET] Nạp thành công {len(samples)} mẫu từ {target_path.name}!")
    return samples
