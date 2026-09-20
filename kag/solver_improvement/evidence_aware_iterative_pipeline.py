# kag/solver/pipeline/evidence_aware_pipeline.py
from kag.interface import SolverPipelineABC, PlannerABC, ExecutorABC, GeneratorABC, Context
from kag.solver.evidence.state import StructuredEvidenceState
from kag.solver.evidence.updater import EvidenceStateUpdater
from kag.solver.evidence.evaluator import EvidenceAwareEvaluator, EvidenceStatus
from kag.solver.evidence.verifier import EvidenceVerifier

@SolverPipelineABC.register("evidence_aware_iterative_pipeline")
class EvidenceAwareIterativePipeline(SolverPipelineABC):
    def __init__(
        self,
        planner: PlannerABC,
        executors: list,
        generator: GeneratorABC,
        max_iteration: int = 5,
        **kwargs
    ):
        super().__init__()
        self.planner = planner
        self.executors = {ex.schema()["name"]: ex for ex in executors}
        self.generator = generator
        self.max_iteration = max_iteration
        
        llm = planner.llm
        self.updater = EvidenceStateUpdater(llm)
        self.evaluator = EvidenceAwareEvaluator(llm)
        self.verifier = EvidenceVerifier(llm)

    async def ainvoke(self, query: str, **kwargs):
        state = StructuredEvidenceState()
        context = Context()
        query_cur = query

        for iteration in range(self.max_iteration):
            # 1. LFPlanner lên kế hoạch cho query_cur
            tasks = await self.planner.ainvoke(query_cur, context=context, **kwargs)
            
            # 2. Reasoner thực thi các tasks
            for task in tasks:
                executor = self.executors.get(task.executor)
                if executor:
                    await executor.ainvoke(query_cur, task, context, **kwargs)
                    context.add_task(task)
                    
                    # 3. Cập nhật Structured Evidence State sau mỗi kết quả
                    state = await self.updater.update(query, state, task.result)

            # 4. Đánh giá trạng thái bằng chứng (Evidence-aware Evaluator)
            status, eval_info = await self.evaluator.evaluate(query, state)

            # Nhánh 1: SUFFICIENT -> Sinh câu trả lời cuối
            if status == EvidenceStatus.SUFFICIENT:
                break

            # Nhánh 4: CONFLICTING -> Verify / Retrieve More -> Vòng lặp tắt thẳng về Reasoner
            elif status == EvidenceStatus.CONFLICTING and state.conflicting_facts:
                conflict = state.conflicting_facts.pop(0)
                verify_task = await self.verifier.create_verification_task(conflict)
                executor = self.executors.get(verify_task.executor)
                if executor:
                    await executor.ainvoke(query, verify_task, context, **kwargs)
                    context.add_task(verify_task)
                    state = await self.updater.update(query, state, verify_task.result)
                continue

            # Nhánh 2 (INCOMPLETE) & Nhánh 3 (UNSUPPORTED) -> SupplyQuery (Reflection / Re-planning)
            elif status in [EvidenceStatus.INCOMPLETE, EvidenceStatus.UNSUPPORTED]:
                hint = eval_info.get("action_hint", "")
                query_cur = f"{query} (Cần làm rõ thêm: {hint})"
                continue

        # 5. Generator tổng hợp Final Answer
        return await self.generator.ainvoke(query, context, **kwargs)