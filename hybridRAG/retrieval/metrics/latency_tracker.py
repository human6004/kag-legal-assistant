import time
from contextlib import contextmanager
from typing import Dict, Optional


class LatencyTracker:
    """
    Bộ theo dõi và đo lường độ trễ (latency tracking/profiling)
    từng giai đoạn trong pipeline RAG:
    - query_rewrite
    - hyde_generation
    - vector_search
    - graph_search
    - hybrid_merge
    - reranking
    - answer_generation
    """

    def __init__(self):
        self.durations: Dict[str, float] = {}
        self._start_total_time: Optional[float] = time.perf_counter()
        self._total_duration: Optional[float] = None

    @contextmanager
    def track(self, stage_name: str):
        start_time = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start_time
            self.durations[stage_name] = round(elapsed, 4)

    def record(self, stage_name: str, duration: float):
        """Ghi nhận trực tiếp giá trị thời gian cho một giai đoạn."""
        self.durations[stage_name] = round(duration, 4)

    def stop_total(self) -> float:
        """Kết thúc đo tổng thời gian pipeline."""
        if self._start_total_time is not None:
            self._total_duration = round(time.perf_counter() - self._start_total_time, 4)
        return self.get_total()

    def get_total(self) -> float:
        """Lấy tổng thời gian (nếu chưa stop_total thì tính từ lúc khởi tạo)."""
        if self._total_duration is not None:
            return self._total_duration
        if self._start_total_time is not None:
            return round(time.perf_counter() - self._start_total_time, 4)
        return round(sum(self.durations.values()), 4)

    def to_dict(self, unit: str = "seconds") -> Dict[str, float]:
        """
        Xuất kết quả đo lường thành dictionary.
        unit: 'seconds' hoặc 'ms'
        """
        multiplier = 1000.0 if unit == "ms" else 1.0
        decimals = 2 if unit == "ms" else 4

        result = {
            stage: round(dur * multiplier, decimals)
            for stage, dur in self.durations.items()
        }
        result["total"] = round(self.get_total() * multiplier, decimals)
        return result

    def summary(self) -> str:
        """Tạo bảng tóm tắt thời gian hiển thị trực quan trên console."""
        total_time = self.get_total()
        lines = [
            "\n" + "=" * 62,
            f"{'GIAI ĐOẠN (PIPELINE STAGE)':<28} | {'THỜI GIAN (s)':<13} | {'(ms)':<8} | {'%':<6}",
            "-" * 62,
        ]

        stage_labels = {
            "query_rewrite": "1. Query Rewrite",
            "hyde_generation": "2. HyDE Generation",
            "vector_search": "3. Vector Search (Chroma)",
            "graph_search": "4. Graph Search (Neo4j)",
            "hybrid_merge": "5. Hybrid Merge",
            "reranking": "6. Cross-Encoder Rerank",
            "answer_generation": "7. LLM Answer Gen",
        }

        for stage, dur in self.durations.items():
            label = stage_labels.get(stage, stage)
            ms = round(dur * 1000.0, 1)
            pct = round((dur / total_time * 100.0), 1) if total_time > 0 else 0.0
            lines.append(f"{label:<28} | {dur:<13.4f} | {ms:<8.1f} | {pct:<5.1f}%")

        lines.append("-" * 62)
        total_ms = round(total_time * 1000.0, 1)
        lines.append(f"{'TỔNG CỘNG (END-TO-END)':<28} | {total_time:<13.4f} | {total_ms:<8.1f} | 100.0%")
        lines.append("=" * 62 + "\n")
        return "\n".join(lines)
