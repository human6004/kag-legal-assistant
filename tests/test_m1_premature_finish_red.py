# -*- coding: utf-8 -*-
"""
Test Suite M1: Nghiên cứu phát hiện lỗ hổng Premature Finish trong KAGIterativePipeline.

Mục tiêu M1 (RED phase):
1. Tái hiện hành vi của baseline KAGIterativePipeline:
   - Khi Planner đề xuất executor "Finish" sau khi mới chỉ lấy được chứng cứ vi phạm (R1),
     baseline chấp nhận ngay lập tức mà không kiểm tra tính đầy đủ của chứng cứ (thiếu khung hình phạt R2).
   - Pipeline kết thúc và chuyển thẳng sang Generator (test_baseline_premature_finish_reaches_generator PASS).
2. Xây dựng chốt kiểm tra độc lập `assert_evidence_sufficiency_gate`:
   - Đánh giá context kết thúc trước Generator.
   - Bắt buộc thất bại với AssertionError do thiếu chứng cứ R2 (test_baseline_premature_finish_fails_evidence_sufficiency_red FAIL / RED).
   - Đảm bảo RED chỉ xuất phát từ thiếu chứng cứ nghiệp vụ, không phải do import, cú pháp hay môi trường.
"""

import sys
import types
import asyncio
import importlib.util
from pathlib import Path
from collections import OrderedDict
from typing import List, Dict, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ==============================================================================
# 1. SETUP STUB CÔ LẬP CHO KAG.INTERFACE
# ==============================================================================
# Tránh import cascade vào pyhocon, ruamel.yaml từ vendor/KAG/kag/__init__.py
# Giữ nguyên interface contract của KAGIterativePipeline:
# SolverPipelineABC, PlannerABC, ExecutorABC, GeneratorABC, Context, Task.

kag_stub = types.ModuleType("kag")
sys.modules["kag"] = kag_stub

kag_interface_stub = types.ModuleType("kag.interface")


class SolverPipelineABC:
    """Stub abstract base class cho Solver Pipeline."""

    @classmethod
    def register(cls, name: str):
        def decorator(subclass):
            return subclass

        return decorator

    def invoke(self, query, **kwargs):
        raise NotImplementedError

    async def ainvoke(self, query, **kwargs):
        raise NotImplementedError


class PlannerABC:
    """Stub abstract base class cho Planner."""

    async def ainvoke(self, query, **kwargs):
        raise NotImplementedError


class ExecutorABC:
    """Stub abstract base class cho Executor với cơ chế registry."""

    _registry: Dict[str, Any] = {}

    def __init__(self, **kwargs):
        pass

    @classmethod
    def register(cls, name: str):
        def decorator(subclass):
            cls._registry[name] = subclass
            return subclass

        return decorator

    @classmethod
    def from_config(cls, cfg: dict):
        exec_type = cfg.get("type")
        if exec_type in cls._registry:
            return cls._registry[exec_type]()
        raise ValueError(f"Unknown executor type: {exec_type}")

    def schema(self) -> Dict[str, Any]:
        return {"name": "BaseExecutor", "description": "", "parameters": {}}

    async def ainvoke(self, query, task, context, **kwargs):
        raise NotImplementedError


class FinishExecutor(ExecutorABC):
    """Executor đánh dấu kết thúc bài toán trong KAGIterativePipeline."""

    def schema(self) -> Dict[str, Any]:
        return {
            "name": "Finish",
            "description": "Performs no operation and is solely used to indicate that the task has been completed.",
            "parameters": {},
        }

    async def ainvoke(self, query, task, context, **kwargs):
        return None


ExecutorABC.register("finish_executor")(FinishExecutor)


class GeneratorABC:
    """Stub abstract base class cho Generator."""

    async def ainvoke(self, query, context, **kwargs):
        raise NotImplementedError


class Task:
    """Cấu trúc biểu diễn Task tương thích với KAG Task."""

    def __init__(
        self,
        executor: str,
        arguments: Optional[dict] = None,
        parents: Optional[List["Task"]] = None,
        children: Optional[List["Task"]] = None,
        id: Optional[str] = None,
        **kwargs,
    ):
        self.executor = executor
        self.arguments = arguments or {}
        self.thought = kwargs.get("thought", "")
        self.status = "PENDING"
        self.id = id or f"task_{executor.lower()}"
        self.parents = parents or []
        self.children = children or []
        self.memory = {}
        self.result = None
        self.name = kwargs.get("name", self.id)

    def __str__(self):
        return f"Task<{self.id}> executor={self.executor} thought={self.thought}"

    __repr__ = __str__


class Context:
    """Context lưu trữ lịch sử các tasks đã thực thi trong pipeline."""

    def __init__(self):
        self._tasks: OrderedDict[str, Task] = OrderedDict()
        self.kwargs: dict = {}

    def add_task(self, task: Task):
        self._tasks[task.id] = task

    def last_task(self) -> Optional[Task]:
        if not self._tasks:
            return None
        last_id = list(self._tasks.keys())[-1]
        return self._tasks[last_id]

    def append_task(self, task: Task):
        if len(task.parents) == 0 and len(self._tasks) > 0:
            last = self.last_task()
            if last:
                task.parents = [last]
        self.add_task(task)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)


# Đăng ký vào stub interface
kag_interface_stub.SolverPipelineABC = SolverPipelineABC
kag_interface_stub.PlannerABC = PlannerABC
kag_interface_stub.ExecutorABC = ExecutorABC
kag_interface_stub.FinishExecutor = FinishExecutor
kag_interface_stub.GeneratorABC = GeneratorABC
kag_interface_stub.Context = Context
kag_interface_stub.Task = Task

sys.modules["kag.interface"] = kag_interface_stub
sys.modules["kag.interface.solver"] = types.ModuleType("kag.interface.solver")
sys.modules["kag.interface.solver.planner_abc"] = kag_interface_stub
sys.modules["kag.interface.solver.context"] = kag_interface_stub
sys.modules["kag.interface.solver.executor_abc"] = kag_interface_stub
sys.modules["kag.interface.solver.pipeline_abc"] = kag_interface_stub
sys.modules["kag.interface.solver.generator_abc"] = kag_interface_stub

# ==============================================================================
# 2. LOAD CLASS KAGIterativePipeline NGUYÊN BẢN TỪ VENDOR/KAG
# ==============================================================================
REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_FILE = (
    REPO_ROOT
    / "vendor"
    / "KAG"
    / "kag"
    / "solver"
    / "pipeline"
    / "kag_iterative_pipeline.py"
)

if not PIPELINE_FILE.exists():
    raise FileNotFoundError(f"Không tìm thấy file pipeline tại: {PIPELINE_FILE}")

spec = importlib.util.spec_from_file_location(
    "kag.solver.pipeline.kag_iterative_pipeline", str(PIPELINE_FILE)
)
pipeline_module = importlib.util.module_from_spec(spec)
sys.modules["kag.solver.pipeline.kag_iterative_pipeline"] = pipeline_module
spec.loader.exec_module(pipeline_module)

KAGIterativePipeline = pipeline_module.KAGIterativePipeline


# ==============================================================================
# 3. FIXTURE TỐI THIỂU CHO M1 (SYNTHETIC LEGAL DATASET)
# ==============================================================================
# LƯU Ý NGHIÊN CỨU: Các trích dẫn, điều khoản và mức phạt dưới đây là DỮ LIỆU TỔNG HỢP
# (SYNTHETIC), được thiết kế độc lập để kiểm chứng luồng logic R1 (có evidence) /
# R2 (thiếu evidence) và chốt chặn kết thúc sớm (Premature Finish).
# KHÔNG sử dụng làm kết luận pháp lý thực tế.

QUERY = (
    "[SYNTHETIC] Hành vi sử dụng AI giả mạo khuôn mặt để xác thực tài khoản ngân hàng "
    "bị xử lý như thế nào theo Nghị định 330/2026/NĐ-CP?"
)

# R1: Quy định hành vi vi phạm (đã thu thập được ở vòng 1)
EVIDENCE_R1 = {
    "id": "R1",
    "dataset_type": "SYNTHETIC",
    "doc": "Nghị định 330/2026/NĐ-CP",
    "article": "Điều 34 khoản 1",
    "chunk_id": "chunk:nd330_2026_dieu34_k1",
    "content": (
        "[SYNTHETIC] Nghiêm cấm sử dụng công nghệ deepfake, trí tuệ nhân tạo (AI) giả mạo dữ liệu "
        "sinh trắc học khuôn mặt để vượt qua các lớp xác thực tài khoản thanh toán hoặc giao dịch ngân hàng."
    ),
}

# Danh mục các yêu cầu chứng cứ bắt buộc để trả lời đầy đủ query
REQUIRED_EVIDENCES = [
    {
        "id": "R1",
        "dataset_type": "SYNTHETIC",
        "description": "Quy định hành vi vi phạm (sử dụng công nghệ deepfake/AI giả mạo dữ liệu sinh trắc học để vượt qua xác thực)",
        "doc": "Nghị định 330/2026/NĐ-CP",
        "article": "Điều 34 khoản 1",
        "expected_chunk_id": "chunk:nd330_2026_dieu34_k1",
    },
    {
        "id": "R2",
        "dataset_type": "SYNTHETIC",
        "description": "Khung hình phạt hành chính cụ thể (phạt tiền 80-100 triệu đồng)",
        "doc": "Nghị định 330/2026/NĐ-CP",
        "article": "Điều 34 khoản 4",
        "expected_chunk_id": None,  # R2 CHƯA ĐƯỢC TRUY XUẤT (bị thiếu trong baseline)
    },
]


# ==============================================================================
# 4. MOCK COMPONENTS ĐIỀU KHIỂN PIPELINE
# ==============================================================================
class ControlledPlanner(PlannerABC):
    """
    Planner được lập trình để mô phỏng lỗ hổng premature finish:
    - Vòng 1: Đề xuất gọi Retriever tìm kiếm quy định vi phạm (lấy được R1).
    - Vòng 2: Vội vã đề xuất Finish dù chưa tìm khung hình phạt (R2).
    """

    def __init__(self):
        self.call_count = 0

    async def ainvoke(self, query: str, context: Context = None, executors=None, **kwargs):
        self.call_count += 1
        if self.call_count == 1:
            return Task(
                executor="Retriever",
                arguments={
                    "query": "Hành vi sử dụng AI giả mạo khuôn mặt xác thực tài khoản ngân hàng Nghị định 330/2026/NĐ-CP"
                },
                thought="Cần truy xuất quy định về hành vi vi phạm sử dụng AI deepfake giả mạo khuôn mặt.",
                id="task_retriever_r1",
            )
        else:
            return Task(
                executor="Finish",
                arguments={},
                thought="Đã tìm thấy quy định vi phạm, hoàn tất.",
                id="task_finish_premature",
            )


class MockRetrieverExecutor(ExecutorABC):
    """Retriever trả về chứng cứ R1 theo fixture."""

    def __init__(self, evidence_list=None):
        super().__init__()
        self.evidence_list = evidence_list or [EVIDENCE_R1]
        self.invoked_tasks = []

    def schema(self) -> Dict[str, Any]:
        return {
            "name": "Retriever",
            "description": "Truy xuất chứng cứ và điều luật từ kho văn bản pháp luật.",
            "parameters": {"query": {"type": "string", "description": "Câu truy vấn"}},
        }

    async def ainvoke(self, query: str, task: Task, context: Context, **kwargs):
        self.invoked_tasks.append(task)
        task.result = {
            "evidence": self.evidence_list,
            "status": "SUCCESS",
        }
        return task.result


class MockGenerator(GeneratorABC):
    """Generator theo dõi xem pipeline có chuyển giao context tới nó hay không."""

    def __init__(self):
        self.called = False
        self.last_query = None
        self.last_context = None

    async def ainvoke(self, query: str, context: Context, **kwargs):
        self.called = True
        self.last_query = query
        self.last_context = context
        return (
            "Theo Điều 34 khoản 1 Nghị định 330/2026/NĐ-CP, hành vi sử dụng AI giả mạo khuôn mặt "
            "để vượt qua xác thực tài khoản ngân hàng là hành vi bị nghiêm cấm."
        )


def create_test_pipeline():
    """Khởi tạo một instance KAGIterativePipeline thực tế kèm các mock components."""
    planner = ControlledPlanner()
    retriever = MockRetrieverExecutor([EVIDENCE_R1])
    generator = MockGenerator()
    pipeline = KAGIterativePipeline(
        planner=planner,
        executors=[retriever],
        generator=generator,
        max_iteration=5,
    )
    return pipeline, planner, retriever, generator


# ==============================================================================
# 5. CHỐT KIỂM CHỨNG CỨ ĐỘC LẬP (EVIDENCE SUFFICIENCY GATE)
# ==============================================================================
def extract_evidences_from_context(context: Context) -> List[Dict[str, Any]]:
    """Trích xuất toàn bộ bằng chứng thu thập được từ context thực thi."""
    evidences = []
    for task in context._tasks.values():
        if task.result and isinstance(task.result, dict):
            task_evidences = task.result.get("evidence", [])
            if isinstance(task_evidences, list):
                evidences.extend(task_evidences)
            elif isinstance(task_evidences, dict):
                evidences.append(task_evidences)
    return evidences


def assert_evidence_sufficiency_gate(
    context: Context, required_evidences: List[Dict[str, Any]]
):
    """
    Chốt kiểm tra tính đầy đủ của chứng cứ (Evidence Sufficiency Gate).

    Đánh giá xem context hiện tại đã thu thập đủ tất cả các chứng cứ bắt buộc hay chưa.
    Nếu bất kỳ chứng cứ bắt buộc nào (như R2 - khung hình phạt) chưa có trong context,
    chốt kiểm tra sẽ nâng AssertionError ngăn chặn kết thúc sớm.
    """
    retrieved = extract_evidences_from_context(context)
    retrieved_chunk_ids = {e.get("chunk_id") for e in retrieved if e.get("chunk_id")}
    retrieved_articles = {e.get("article") for e in retrieved if e.get("article")}

    missing = []
    for req in required_evidences:
        article = req.get("article")
        expected_chunk = req.get("expected_chunk_id")
        has_chunk = bool(expected_chunk and expected_chunk in retrieved_chunk_ids)
        has_article = bool(article and article in retrieved_articles)
        if not (has_chunk or has_article):
            missing.append(req)

    if missing:
        missing_details = "; ".join(
            f"{m['id']} ({m['description']} - {m.get('doc', '')} {m.get('article', '')})"
            for m in missing
        )
        raise AssertionError(
            f"[Evidence Sufficiency Gate FAILED] Context chưa đủ chứng cứ để kết thúc và sinh câu trả lời! "
            f"Thiếu các chứng cứ bắt buộc: [{missing_details}]. "
            f"Chứng cứ hiện có: {list(retrieved_articles)}."
        )


# ==============================================================================
# 6. TEST CASES CHỨNG MINH M1
# ==============================================================================
def test_baseline_premature_finish_reaches_generator():
    """
    Điều 1 (GREEN): Chứng minh baseline KAGIterativePipeline chấp nhận 'Finish'
    và tiến tới Generator dù chứng cứ R2 (Khung hình phạt) hoàn toàn vắng mặt.
    """

    async def _run():
        pipeline, planner, retriever, generator = create_test_pipeline()
        answer = await pipeline.ainvoke(QUERY)

        # Baseline KAG chấp nhận Finish và gọi Generator
        assert generator.called is True, "Generator phải được gọi trong baseline khi Finish"
        assert generator.last_context is not None, "Context phải được chuyển giao tới Generator"

        # Kiểm tra thứ tự thực thi trong context: Vòng 1 Retriever, Vòng 2 Finish
        task_list = list(generator.last_context._tasks.values())
        assert len(task_list) == 2, f"Kỳ vọng 2 tasks trong context, thực tế: {len(task_list)}"
        assert task_list[0].executor == "Retriever"
        assert task_list[1].executor == "Finish"
        assert task_list[1].thought == "Đã tìm thấy quy định vi phạm, hoàn tất."

        # Chứng minh bằng chứng thu thập được chỉ có R1, thiếu hoàn toàn R2
        evidences = extract_evidences_from_context(generator.last_context)
        retrieved_articles = [e.get("article") for e in evidences]
        assert "Điều 34 khoản 1" in retrieved_articles, "Phải có chứng cứ R1 (Điều 34 khoản 1)"
        assert (
            "Điều 34 khoản 4" not in retrieved_articles
        ), "Chứng cứ R2 (Điều 34 khoản 4) không được có mặt trong baseline"

        # Câu trả lời được tạo ra dù thiếu khung hình phạt
        assert answer is not None
        assert "Điều 34 khoản 1" in answer

    asyncio.run(_run())


def test_baseline_premature_finish_fails_evidence_sufficiency_red():
    """
    Điều 2 (RED): Chứng minh chốt kiểm tra độc lập (assert_evidence_sufficiency_gate)
    thất bại với AssertionError vì context cuối cùng thiếu chứng cứ R2.
    """

    async def _run():
        pipeline, planner, retriever, generator = create_test_pipeline()
        # Chạy pipeline baseline
        await pipeline.ainvoke(QUERY)

        # Đánh giá context kết thúc qua chốt kiểm tra độc lập
        # Lời gọi này BẮT BUỘC RAISE AssertionError (RED) do thiếu R2
        assert_evidence_sufficiency_gate(generator.last_context, REQUIRED_EVIDENCES)

    asyncio.run(_run())


# ==============================================================================
# 7. CHẠY TRỰC TIẾP QUA PYTHON CLI
# ==============================================================================
if __name__ == "__main__":
    print("=== [M1 TEST SUITE] BẮT ĐẦU KIỂM TRA PREMATURE FINISH VÀ EVIDENCE SUFFICIENCY ===")

    print("\n--- 1. Chạy test_baseline_premature_finish_reaches_generator ---")
    try:
        test_baseline_premature_finish_reaches_generator()
        print(">> PASS: Baseline KAGIterativePipeline chấp nhận Finish và tiến tới Generator thành công.")
    except Exception as e:
        print(f">> FAIL BẤT THƯỜNG: {e}")
        sys.exit(1)

    print("\n--- 2. Chạy test_baseline_premature_finish_fails_evidence_sufficiency_red (RED TEST) ---")
    try:
        test_baseline_premature_finish_fails_evidence_sufficiency_red()
        print(">> UNEXPECTED PASS: Lẽ ra phải fail vì thiếu R2!")
        sys.exit(1)
    except AssertionError as e:
        print(f">> RED THÀNH CÔNG (AssertionError như mong đợi):\n   {e}")
        print("\n=== KẾT QUẢ: Xác nhận RED chuẩn xác. Không có lỗi import, syntax hay môi trường. ===")
