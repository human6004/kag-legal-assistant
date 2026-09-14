# Copyright 2023 OpenSPG Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.

import os
import sys
import signal
import logging
import threading
from kag.common.registry import import_modules_from_path
from kag.builder.runner import BuilderChainRunner
from kag.interface.builder.base import BuilderComponent

logger = logging.getLogger(__name__)


# --- Dung sach bang Ctrl+C -------------------------------------------------
# runner.invoke dung `with ThreadPoolExecutor(...)`, nen KeyboardInterrupt roi
# vao shutdown(wait=True): no CHO het moi future da submit roi moi thoat, nhin
# nhu treo. ThreadPoolExecutor cung khong huy duoc future dang chay.
# Cach re nhat: mot co hop tac. Moi chunk di qua BuilderComponent.invoke o
# moi buoc (reader / splitter / extractor / vectorizer / post_processor /
# writer), nen chan ngay dau ham la bo hang doi rat nhanh.
# Tra ve [] TRUOC khi _invoke chay, tuc la khong ghi checkpoint rong -> lan
# chay lai van lam that, khong bi cache danh lua.
# GIOI HAN: day la dung HOP TAC, khong phai ep chet. Chunk dang nam trong mot
# request HTTP van chay het timeout cua no (90s LLM / 60s embedding). Va vi
# luong chinh van thoat qua `with ThreadPoolExecutor`, khong co so lan bam
# Ctrl+C nao ep chet duoc -> muon chet ngay thi taskkill, xem _kill_hint().
_stop = threading.Event()
_orig_invoke = BuilderComponent.invoke

# --- Cau dao khi gateway chet -----------------------------------------------
# default_chain.py bat exception cua tung chunk roi chay tiep, nen het quota /
# sai key KHONG lam build dung: no bo trang toan bo chunk con lai roi bao
# "0 failures". Va moi chunk hong ton ~120s cho retry long hai tang
# (call_with_json_parse 3 lan 10s/20s, ben ngoai named_entity_recognition 3 lan
# nua) -> ca kho la ~2,5 tieng quay khong tai.
# Dem so lan hong LIEN TIEP: mot chunk chay duoc la reset ve 0, nen loi le te do
# LLM tra JSON xau khong bao gio cham nguong. Chi su co he thong moi cham.
_FAIL_LIMIT = 12
_fail_lock = threading.Lock()
_fail_streak = 0


def _invoke_with_stop(self, input, **kwargs):
    global _fail_streak
    if _stop.is_set():
        return []
    try:
        out = _orig_invoke(self, input, **kwargs)
    except Exception:
        with _fail_lock:
            _fail_streak += 1
            streak = _fail_streak
        if streak >= _FAIL_LIMIT and not _stop.is_set():
            _stop.set()
            print("", flush=True)
            print(
                "[cau dao] %d chunk hong lien tiep -> nghi gateway/quota/key chet. "
                "Dung build de khoi dot thoi gian." % streak,
                flush=True,
            )
            print(
                "[cau dao] Chunk da xong van nam trong ckpt. Sua xong chay lai "
                "dung lenh cu, no chi lam phan con thieu.",
                flush=True,
            )
        raise
    with _fail_lock:
        _fail_streak = 0
    return out


def _kill_hint():
    # Ctrl+C KHONG ep chet duoc: du co ban va nay, luong chinh van thoat qua
    # `with ThreadPoolExecutor(...)` -> shutdown(wait=True) -> cho het luong.
    # Nen dua thang lenh giet kem PID that, khoi phai di tim.
    return "taskkill /PID %d /T /F" % os.getpid()


def _on_sigint(signum, frame):
    if _stop.is_set():
        print(
            "[dung] Da bat co roi, dang cho cac chunk dang chay. Ctrl+C them "
            "KHONG ep chet duoc. Muon chet ngay thi mo cua so khac va chay:",
            flush=True,
        )
        print("[dung]   " + _kill_hint(), flush=True)
        return
    _stop.set()
    print("", flush=True)
    print(
        "[dung] Da nhan Ctrl+C. Cho cac chunk dang goi LLM chay not "
        "(toi da ~90s theo timeout). Phan da xong van nam trong Neo4j va kag/ckpt/.",
        flush=True,
    )
    print("[dung] Chay lai dung lenh cu de tiep tuc.", flush=True)
    print("[dung] Het kien nhan thi: " + _kill_hint(), flush=True)


def install_stop_handler():
    BuilderComponent.invoke = _invoke_with_stop
    signal.signal(signal.SIGINT, _on_sigint)


def buildKB(dir_path):
    from kag.common.conf import KAG_CONFIG

    runner = BuilderChainRunner.from_config(
        KAG_CONFIG.all_config["kag_builder_pipeline"]
    )
    runner.invoke(dir_path)

    logger.info(f"\n\nbuildKB successfully for {dir_path}\n\n")


if __name__ == "__main__":
    dir_path = os.path.dirname(os.path.abspath(__file__))
    import_modules_from_path(dir_path)
    install_stop_handler()

    # Truyen duong dan de chay thu mot thu muc nho truoc khi dot tien ca kho:
    #     python builder/indexer.py ../data/trial
    default_path = os.path.join(dir_path, "..", "..", "data", "processed")
    buildKB(sys.argv[1] if len(sys.argv) > 1 else default_path)
