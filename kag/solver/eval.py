import logging
from typing import List

from kag.common.conf import KAG_CONFIG
from kag.interface import SolverPipelineABC
from kag.open_benchmark.utils.eval_qa import EvalQa, do_main
from kag.solver.reporter.trace_log_reporter import TraceLogReporter

logger = logging.getLogger(__name__)


def norm_text(s: str) -> str:
    """Chuan hoa truoc khi so khop chuoi con.

    Ba viec, moi viec deu sua mot loi da gap that:

    1. NFC. Tieng Viet co hai cach ma hoa cung mot chu: "o" + dau huyen (NFD,
       2 diem ma) va "o" da ghep san (NFC, 1 diem ma). Nhin y het nhau nhung
       so sanh chuoi thi khac. Nguon o day la markdown doc tu PDF, con cau tra
       loi do mo hinh sinh ra, hai ben khong ai bao dam cung dang. Do lan nay
       ca hai deu NFC nen chua no, nhung doi mo hinh hoac doi nguon la no cam.
    2. Bo ky tu markdown. Mo hinh hay in dam "**cham nhat la 24 gio**" va ranh
       gioi ** roi vao GIUA moc, sinh ra "cham nhat la 24 gio** ke tu...".
       Khong bo * thi moc truot oan du cau tra loi dung hoan toan. Da dinh
       that o cau 2 luot chay thu 5 cau.
    3. Bo khoang trang, dau cham, dau phay. De "30.000.000" va "30 000 000"
       deu trung nhau.
    """
    import unicodedata

    s = unicodedata.normalize("NFC", s)
    for ch in "*`#_|":
        s = s.replace(ch, "")
    return "".join(s.split()).replace(".", "").replace(",", "").lower()


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
        file_path = os.path.join(dir_path, "questions_mo_rong.json")
        with io.open(file_path, "r", encoding="utf-8", newline="\n") as fin:
            questions = json.load(fin)
        return questions

    def do_metrics_eval(
        self, questionList: List[str], predictions: List[str], golds: List[str]
    ):
        # hit3/hit5/hitall den tu do_recall_eval cua lop cha, lop cha tra
        # {"recall": None} -> luon 0. Xem recall_report.py de biet cach dung
        # lai chung tu gold chunk sinh ra boi gold_chunks.py.
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

        pred = norm_text(predictions[0] or "")
        hit = sum(1 for g in gold if norm_text(g) in pred)
        return {"hit_rate": hit / len(gold), "hit_all": float(hit == len(gold))}


def _nap_prompt_theo_duong_dan(thu_muc: str) -> None:
    """Nap moi file .py trong thu_muc duoi ten module rieng biet.

    Dung thay import_modules_from_path khi ten thu muc co the trung voi mot goi
    da nam trong sys.modules. O day thu_muc la "prompt", trung dung voi
    kag/solver/prompt, nen import_modules_from_path se lang le bo qua no.

    Khong can goi importlib.import_module: cac file trong thu_muc tu goi
    @PromptABC.register("legal_xxx") ngay o cap module, chi can thuc thi file
    la dang ky xong. Ten module duoc dat tien to de khong bao gio trung.
    """
    import glob
    import importlib.util
    import os
    import sys

    for duong_dan in sorted(glob.glob(os.path.join(thu_muc, "*.py"))):
        ten_file = os.path.splitext(os.path.basename(duong_dan))[0]
        if ten_file == "__init__" or ten_file.startswith("check_"):
            continue
        ten_module = f"_legal_builder_prompt_{ten_file}"
        if ten_module in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(ten_module, duong_dan)
        module = importlib.util.module_from_spec(spec)
        sys.modules[ten_module] = module
        spec.loader.exec_module(module)
        logger.info(f"da nap prompt tu file: {duong_dan}")


def main():
    import os
    import sys
    from kag.common.registry import import_modules_from_path

    # eval_qa.py:53 in nguyen van cau hoi ra stdout bang print() tran. Tren Windows
    # console mac dinh la cp1252, gap chu co dau la UnicodeEncodeError -> cau hoi
    # do "process sample failed" va processNum tut ve 0, du dap an da co trong
    # legal_ckpt va khong he goi lai LLM. Ep UTF-8 ngay o day thay vi sua KAG.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    dir_path = os.path.dirname(os.path.abspath(__file__))
    import_modules_from_path(dir_path)

    # legal_std/legal_ner/legal_triple nam ben builder/prompt. KHONG dung
    # import_modules_from_path cho thu muc do: ham nay lay TEN THU MUC CUOI lam
    # ten module (utils.py:44 `package_name`), ca hai thu muc deu ten "prompt",
    # nen lan goi thu hai bi sys.modules["prompt"] chan va tra ve module cu.
    # Ket qua: legal_std khong bao gio duoc dang ky, PromptABC roi ve default_std
    # tieng Anh, chi log INFO "not in acceptable choices" nen rat kho thay.
    # Da do bang probe: sys.modules['prompt'].__file__ van tro ve kag/solver/prompt
    # sau lan import thu hai, va ca ba ten legal_* deu "KHONG DANG KY".
    # Cach sua: nap thang tung file duoi ten module rieng, khong cham sys.modules
    # ["prompt"]. An toan vi ba file trong do chi import kag.interface + json,
    # khong file nao import noi bo trong goi (da kiem tra).
    _nap_prompt_theo_duong_dan(
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
        thread_num=8,
        upper_limit=5,
        collect_file="benchmark.txt",
        eval_obj=LegalEvaluator(),
    )


if __name__ == "__main__":
    main()
