# -*- coding: utf-8 -*-
"""Tầng adapter chuyển đổi quan hệ an toàn giữa Ontology Schema (v2) và Graph v1.

Nguyên tắc bắt buộc:
1. KHÔNG tự đoán hoặc gộp quan hệ khi chưa có bằng chứng pháp lý hai chiều.
2. Tên quan hệ camel-case tiếng Việt không khả nghịch: TUYỆT ĐỐI KHÔNG tự động đổi
   tên tiếng Việt méo dấu sang quan hệ schema (ví dụ: thuCVNBN -> belongsTo).
3. Chặn (block) mọi truy vấn graph đối với các quan hệ chưa được ánh xạ / chưa hỗ trợ.
4. Khi không có dữ liệu quan hệ đáng tin (live graph / audited snapshot vắng mặt),
   phải FAIL CLOSED và nêu rõ lý do, không dùng tập quan hệ giả định.
5. Cung cấp chốt chặn chung (guard hook) can thiệp trực tiếp vào đường chạy thực thi
   của KAGHybridRetrievalExecutor, ExactOneHopSelect, và FuzzyOneHopSelect.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

class RelationResolutionStatus:
    SUPPORTED_DIRECT = "SUPPORTED_DIRECT"                      # Tồn tại trực tiếp trong đồ thị mục tiêu
    UNSUPPORTED_BLOCKED = "UNSUPPORTED_BLOCKED"                # Chưa được hỗ trợ / chưa ánh xạ, chặn truy vấn an toàn
    NO_TRUSTED_METADATA_FAIL_CLOSED = "NO_TRUSTED_METADATA_FAIL_CLOSED"  # Thiếu metadata quan hệ đáng tin, chặn an toàn


class SafeRelationAdapter:
    """Adapter xử lý kiểm tra và chặn an toàn quan hệ trước khi gửi truy vấn đồ thị."""

    def __init__(self, live_predicates: Optional[Set[str]] = None, audit_edges_path: Optional[str] = None):
        if live_predicates is not None:
            self.live_predicates = set(live_predicates)
        else:
            # Nạp từ snapshot đối chứng nếu có
            target_path = Path(audit_edges_path) if audit_edges_path else (
                Path(__file__).resolve().parents[2] / "dist" / "audit-2026-09-17" / "edges.json"
            )
            if target_path.exists():
                try:
                    edges_data = json.loads(target_path.read_text(encoding="utf-8"))
                    self.live_predicates = set(e["type"] for e in edges_data if "type" in e)
                except Exception as ex:
                    logger.warning(f"Không thể đọc edges từ {target_path}: {ex}")
                    self.live_predicates = None
            else:
                self.live_predicates = None

    def resolve_predicate_for_graph_v1(
        self, predicate: str, source_label: Optional[str] = None, target_label: Optional[str] = None
    ) -> Tuple[str, Optional[str], str]:
        """Phân giải và kiểm tra vị ngữ trước khi truy vấn đồ thị.
        
        Returns:
            (status, resolved_predicate_name, explanation)
        """
        if self.live_predicates is None:
            return (
                RelationResolutionStatus.NO_TRUSTED_METADATA_FAIL_CLOSED,
                None,
                f"Không có dữ liệu quan hệ đáng tin từ đồ thị thực tế. Fail-closed: Chặn truy vấn với vị ngữ '{predicate}'."
            )

        if predicate in self.live_predicates:
            return (
                RelationResolutionStatus.SUPPORTED_DIRECT,
                predicate,
                f"Vị ngữ '{predicate}' tồn tại trực tiếp trong đồ thị thực tế."
            )

        return (
            RelationResolutionStatus.UNSUPPORTED_BLOCKED,
            None,
            f"Vị ngữ '{predicate}' là quan hệ Schema nhưng không tồn tại trong Graph V1 "
            f"và chưa có bảng ánh xạ được chứng minh. Hệ thống chặn truy vấn để tránh sai lệch."
        )

    def validate_query_plan(self, actions: List[Dict]) -> Dict:
        """Kiểm tra toàn bộ kế hoạch truy vấn trước khi thực thi."""
        blocked_actions = []
        for idx, act in enumerate(actions):
            pred = act.get("predicate") or act.get("p")
            if pred:
                status, resolved, msg = self.resolve_predicate_for_graph_v1(pred)
                if status != RelationResolutionStatus.SUPPORTED_DIRECT:
                    blocked_actions.append({
                        "step_index": idx,
                        "action": act,
                        "status": status,
                        "reason": msg
                    })
        return {
            "is_executable": len(blocked_actions) == 0,
            "blocked_count": len(blocked_actions),
            "blocked_details": blocked_actions
        }


# Global adapter instance
_GLOBAL_ADAPTER: Optional[SafeRelationAdapter] = None

def get_global_adapter() -> SafeRelationAdapter:
    global _GLOBAL_ADAPTER
    if _GLOBAL_ADAPTER is None:
        _GLOBAL_ADAPTER = SafeRelationAdapter()
    return _GLOBAL_ADAPTER

def set_global_adapter(adapter: SafeRelationAdapter):
    global _GLOBAL_ADAPTER
    _GLOBAL_ADAPTER = adapter


def install_safe_guard(adapter: Optional[SafeRelationAdapter] = None):
    """Cài đặt chốt chặn an toàn trực tiếp vào các điểm nghẽn thực thi đồ thị của KAG."""
    if adapter is not None:
        set_global_adapter(adapter)

    # 1. Chốt chặn tại KAGHybridRetrievalExecutor.invoke
    try:
        from kag.solver.executor.retriever.kag_hybrid_retrieval_executor import KAGHybridRetrievalExecutor
        from kag.common.parser.logic_node_parser import GetSPONode
        from kag.interface import RetrieverOutput

        if not getattr(KAGHybridRetrievalExecutor, "_safe_guard_installed", False):
            orig_executor_invoke = KAGHybridRetrievalExecutor.invoke

            def guarded_executor_invoke(self, query, task, context, **kwargs):
                logic_node = task.arguments.get("logic_form_node", None)
                if logic_node and isinstance(logic_node, GetSPONode) and logic_node.p:
                    pred = logic_node.p.get_entity_first_type_or_un_std()
                    if pred:
                        active_adapter = get_global_adapter()
                        status, _, msg = active_adapter.resolve_predicate_for_graph_v1(pred)
                        if status != RelationResolutionStatus.SUPPORTED_DIRECT:
                            logger.warning(f"[SAFE_GUARD_BLOCKED_TASK] {msg}")
                            output = RetrieverOutput()
                            output.summary = f"[BLOCKED] {msg}"
                            task.update_result(output)
                            return output

                return orig_executor_invoke(self, query, task, context, **kwargs)

            KAGHybridRetrievalExecutor.invoke = guarded_executor_invoke
            KAGHybridRetrievalExecutor._safe_guard_installed = True
            logger.info("Đã gắn chốt chặn SafeRelationAdapter vào KAGHybridRetrievalExecutor.invoke")
    except Exception as e:
        logger.debug(f"Chưa thể gắn chốt chặn KAGHybridRetrievalExecutor: {e}")

    # 2. Chốt chặn tại ExactOneHopSelect.invoke và FuzzyOneHopSelect.invoke
    try:
        from kag.common.tools.algorithm_tool.graph_retriever.path_select.exact_one_hop_select import ExactOneHopSelect
        from kag.common.tools.algorithm_tool.graph_retriever.path_select.fuzzy_one_hop_select import FuzzyOneHopSelect
        from kag.common.parser.logic_node_parser import GetSPONode

        for cls in (ExactOneHopSelect, FuzzyOneHopSelect):
            if not getattr(cls, "_safe_guard_installed", False):
                orig_cls_invoke = cls.invoke

                def make_guarded_invoke(orig_fn):
                    def guarded_path_invoke(self, query, spo, heads, tails, **kwargs):
                        if spo and isinstance(spo, GetSPONode) and spo.p:
                            pred = spo.p.get_entity_first_type_or_un_std()
                            if pred:
                                active_adapter = get_global_adapter()
                                status, _, msg = active_adapter.resolve_predicate_for_graph_v1(pred)
                                if status != RelationResolutionStatus.SUPPORTED_DIRECT:
                                    logger.warning(f"[SAFE_GUARD_BLOCKED_PATH_SELECT] {msg}")
                                    return []

                        return orig_fn(self, query, spo, heads, tails, **kwargs)
                    return guarded_path_invoke

                cls.invoke = make_guarded_invoke(orig_cls_invoke)
                cls._safe_guard_installed = True
                logger.info(f"Đã gắn chốt chặn SafeRelationAdapter vào {cls.__name__}.invoke")
    except Exception as e:
        logger.debug(f"Chưa thể gắn chốt chặn PathSelect subclasses: {e}")
