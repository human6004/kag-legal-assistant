"""
Claim-level Groundedness & Hallucination Auditing Module
Tuân thủ các nguyên lý cốt lõi tại Chapter 6.1.1, Appendix E.2 & E.4
trong sách "RAG Evaluation & Testing in Production" (Lamhot Siagian, 2026).

Nguyên tắc:
1. Phân rã câu trả lời thành các mệnh đề nguyên tử (Atomic Claims).
2. Kiểm tra từng claim đối chiếu với ngữ cảnh thực tế được truy xuất (Retrieved Context).
3. Đánh dấu nhãn:
   - SUPPORTED: Ngữ cảnh chứng minh rõ ràng.
   - UNSUPPORTED: Không có bằng chứng trong ngữ cảnh (Extrinsic Hallucination).
   - CONTRADICTED: Trái ngược với ngữ cảnh (Intrinsic Hallucination).
4. Phân loại Critical Error:
   - Liều lượng sai (pha thuốc nấm, nồng độ phân bón).
   - Sai tên thuốc hoặc hướng dẫn gây ngộ độc rễ.
5. Groundedness Score = (Số claims SUPPORTED) / (Tổng số claims).
"""

import re
from typing import List, Dict, Any, Optional, Tuple


def decompose_into_atomic_claims(text: str) -> List[str]:
    """
    Tách đoạn văn bản thành các câu/mệnh đề độc lập (Atomic Claims).
    Xử lý danh sách gạch đầu dòng, dấu chấm câu, liên từ đẳng lập.
    """
    if not text:
        return []

    # Chuẩn hóa các dấu xuống dòng và dấu phân cách câu
    raw_lines = text.replace("\r\n", "\n").split("\n")
    sentences = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        # Loại bỏ tiền tố bullet point, số thứ tự
        cleaned = re.sub(r"^(\*|-|\+|\d+\.)\s+", "", line).strip()
        if not cleaned:
            continue
        # Tách tiếp theo dấu chấm câu hoặc chấm phẩy
        sub_sents = re.split(r"(?<=[.!?;\n])\s+", cleaned)
        for s in sub_sents:
            s_clean = s.strip()
            # Bỏ các câu quá ngắn vô nghĩa như "Cụ thể là:" hoặc "Như sau:"
            if len(s_clean.split()) >= 3:
                sentences.append(s_clean)

    return sentences if sentences else [text.strip()]


def verify_claim_against_context(
    claim: str,
    context_text: str,
    critical_keywords: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Xác minh 1 claim có được hỗ trợ bởi context hay không.
    Kiểm tra cả việc claim có chứa thông tin nguy hiểm (Critical Error) không.
    """
    claim_lower = claim.lower()
    context_lower = context_text.lower()

    if not context_lower:
        return {
            "claim": claim,
            "status": "UNSUPPORTED",
            "is_critical": False,
            "evidence_snippet": ""
        }

    # 1. Trích xuất các thực thể quan trọng trong claim (số liệu liều lượng, tên thuốc, thao tác)
    # Tìm liều lượng: ví dụ 2gram/lít, 10g, 50ml, 5-10 ngày, 3 tháng...
    dosage_patterns = re.findall(r"\b\d+[\.,]?\d*\s*(?:gram|g|ml|lít|ngày|tháng|ly|%)\b", claim_lower)
    # Tìm tên thuốc nấm / hóa chất
    chemical_keywords = [
        "coc85", "champion", "ridomil gold", "anvil", "trichoderma",
        "metalaxyl", "mancozeb", "n3m", "karate", "delfin"
    ]
    matched_chemicals = [c for c in chemical_keywords if c in claim_lower]

    is_critical_claim = len(dosage_patterns) > 0 or len(matched_chemicals) > 0

    # 2. Kiểm tra mức độ bao hàm ngữ nghĩa (Semantic & Lexical Containment)
    # Tách claim thành các từ vựng mang nội dung (bỏ stop words tiếng Việt cơ bản)
    vietnamese_stopwords = {
        "là", "của", "và", "có", "được", "cho", "trong", "để", "với", "các", "những",
        "thì", "này", "khi", "lại", "ra", "vào", "ở", "nếu", "sẽ", "đã", "đang", "cần",
        "nên", "thường", "theo", "sau", "từ", "lên", "xuống", "như", "một", "bị", "do"
    }
    claim_words = [w for w in re.findall(r"\w+", claim_lower) if w not in vietnamese_stopwords and len(w) > 1]

    if not claim_words:
        return {
            "claim": claim,
            "status": "SUPPORTED",
            "is_critical": False,
            "evidence_snippet": ""
        }

    # Kiểm tra xem các từ cốt lõi có trong context không
    matched_words = [w for w in claim_words if w in context_lower]
    coverage = len(matched_words) / len(claim_words)

    # Nếu claim có số liệu liều lượng, kiểm tra xem số liệu đó có khớp trong context không
    dosage_mismatch = False
    if dosage_patterns:
        for d in dosage_patterns:
            # Chuẩn hóa khoảng trắng để tìm chính xác
            d_norm = re.sub(r"\s+", "", d)
            ctx_condensed = re.sub(r"\s+", "", context_lower)
            if d_norm not in ctx_condensed:
                dosage_mismatch = True
                break

    # Phân loại trạng thái
    if dosage_mismatch:
        status = "CONTRADICTED"
        is_critical = True
    elif coverage >= 0.60:
        # Trên 60% từ khóa nội dung xuất hiện trong context
        status = "SUPPORTED"
        is_critical = False
    elif coverage >= 0.35:
        # Một phần, nhưng thiếu căn cứ xác thực đầy đủ
        status = "UNSUPPORTED"
        is_critical = is_critical_claim
    else:
        status = "UNSUPPORTED"
        is_critical = is_critical_claim

    return {
        "claim": claim,
        "status": status,
        "is_critical": is_critical,
        "matched_coverage": round(coverage, 3),
        "dosage_patterns": dosage_patterns,
        "matched_chemicals": matched_chemicals
    }


def evaluate_claim_groundedness(
    answer: str,
    retrieved_contexts: List[str]
) -> Dict[str, Any]:
    """
    Đánh giá độ trung thực (Groundedness) ở cấp độ từng mệnh đề (Claim-level)
    theo chuẩn Chapter 6.1.1 của Lamhot Siagian.
    
    Returns:
        {
            "groundedness_score": float (0.0 - 1.0),
            "total_claims": int,
            "supported_claims": int,
            "unsupported_claims": int,
            "contradicted_claims": int,
            "has_critical_error": bool,
            "critical_claims": List[Dict],
            "claims_detail": List[Dict]
        }
    """
    if not answer or answer.strip() == "":
        return {
            "groundedness_score": 0.0,
            "total_claims": 0,
            "supported_claims": 0,
            "unsupported_claims": 0,
            "contradicted_claims": 0,
            "has_critical_error": False,
            "critical_claims": [],
            "claims_detail": []
        }

    # Gom toàn bộ context đã truy xuất lại làm căn cứ chứng minh
    combined_context = "\n".join(retrieved_contexts)

    # 1. Phân rã claims
    claims = decompose_into_atomic_claims(answer)
    if not claims:
        return {
            "groundedness_score": 1.0,
            "total_claims": 0,
            "supported_claims": 0,
            "unsupported_claims": 0,
            "contradicted_claims": 0,
            "has_critical_error": False,
            "critical_claims": [],
            "claims_detail": []
        }

    # 2. Thẩm định từng claim
    supported_count = 0
    unsupported_count = 0
    contradicted_count = 0
    critical_claims = []
    claims_detail = []

    for c in claims:
        verdict = verify_claim_against_context(c, combined_context)
        status = verdict["status"]
        if status == "SUPPORTED":
            supported_count += 1
        elif status == "UNSUPPORTED":
            unsupported_count += 1
        elif status == "CONTRADICTED":
            contradicted_count += 1

        if verdict["is_critical"] and status in ("UNSUPPORTED", "CONTRADICTED"):
            critical_claims.append(verdict)

        claims_detail.append(verdict)

    total = len(claims)
    groundedness = round(supported_count / total, 4) if total > 0 else 0.0

    return {
        "groundedness_score": groundedness,
        "total_claims": total,
        "supported_claims": supported_count,
        "unsupported_claims": unsupported_count,
        "contradicted_claims": contradicted_count,
        "has_critical_error": len(critical_claims) > 0,
        "critical_claims": critical_claims,
        "claims_detail": claims_detail
    }
