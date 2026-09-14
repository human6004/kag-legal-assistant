import logging
from typing import List

from kag.common.conf import KAG_CONFIG
from kag.interface import SolverPipelineABC
from kag.open_benchmark.utils.eval_qa import EvalQa, do_main
from kag.solver.reporter.trace_log_reporter import TraceLogReporter

logger = logging.getLogger(__name__)


class LegalEvaluator(EvalQa):
    def __init__(self, solver_pipeline_name="kag_solver_pipeline"):
        self.task_name = "legal"
        super().__init__(self.task_name, solver_pipeline_name)
        self.solver_pipeline_name = solver_pipeline_name

    def get_question(self, sample):
        return sample["input"]

    def get_answer(self, sample):
        return sample["answers"]

    async def qa(self, query, gold):
        reporter: TraceLogReporter = TraceLogReporter()
        pipeline = SolverPipelineABC.from_config(
            KAG_CONFIG.all_config[self.solver_pipeline_name]
        )
        answer = await pipeline.ainvoke(query, reporter=reporter, gold=gold)

        logger.info(f"\n\nso the answer for '{query}' is: {answer}\n\n")

        info, status = reporter.generate_report_data()
        return answer, {"info": info.to_dict(), "status": status}

    def load_data(self, file_path):
        import io
        import os
        import json

        dir_path = os.path.dirname(os.path.abspath(__file__))
        dir_path = os.path.join(dir_path, "data")
        file_path = os.path.join(dir_path, "questions.json")
        with io.open(file_path, "r", encoding="utf-8", newline="\n") as fin:
            questions = json.load(fin)
        return questions

    def do_metrics_eval(
        self, questionList: List[str], predictions: List[str], golds: List[str]
    ):
        # hit3/hit5/hitall trong ket qua KHONG doc cho nay: chung den tu
        # do_recall_eval cua lop cha, ma lop cha tra {"recall": None} -> luon 0.
        # Muon chung chay thi questions.json phai co san id chunk dung, chua co.
        # Day la duong duy nhat hien gio de "answers" co tac dung.
        #
        # golds[0] la list cac moc phai xuat hien trong cau tra loi (so tien, so
        # dieu). So khop bang substring, bo dau cham/khoang trang cho "30.000.000"
        # va "30 000 000" deu trung.
        gold = golds[0] if golds else []
        if isinstance(gold, str):
            gold = [gold]
        # bo placeholder "<dien dap an dung...>" de khong tao diem gia
        gold = [g for g in gold if g and not g.startswith("<")]
        if not gold:
            return {}

        def norm(s):
            return "".join(s.split()).replace(".", "").replace(",", "").lower()

        pred = norm(predictions[0] or "")
        hit = sum(1 for g in gold if norm(g) in pred)
        return {"hit_rate": hit / len(gold), "hit_all": float(hit == len(gold))}


def main():
    import os
    from kag.common.registry import import_modules_from_path

    dir_path = os.path.dirname(os.path.abspath(__file__))
    import_modules_from_path(dir_path)
    # legal_std nam ben builder/prompt; khong import thi PromptABC roi ve
    # default_std (tieng Anh) im lang, chi log INFO "not in acceptable choices".
    import_modules_from_path(
        os.path.join(os.path.dirname(dir_path), "builder", "prompt")
    )

    # eval_qa.py dat ten file ket qua bang duong dan TUONG DOI (eval_main:232-233
    # va ckpt_dir o parallel_qa_and_evaluate), nen moi lan chay lai vut them
    # legal_metrics_*.json + legal_res_*.json (~370KB/lan) ngay canh eval.py.
    # Doi cwd truoc khi goi do_main la du de gom het vao runs/, khong phai dung
    # den KAG. load_data van chay dung vi no dung duong dan tuyet doi tu __file__.
    os.makedirs(os.path.join(dir_path, "runs"), exist_ok=True)
    os.chdir(os.path.join(dir_path, "runs"))

    do_main(
        qa_file_path="",
        thread_num=20,
        upper_limit=5,
        collect_file="benchmark.txt",
        eval_obj=LegalEvaluator(),
    )


if __name__ == "__main__":
    main()
