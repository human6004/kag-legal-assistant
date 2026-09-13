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
_stop = threading.Event()
_orig_invoke = BuilderComponent.invoke


def _invoke_with_stop(self, input, **kwargs):
    if _stop.is_set():
        return []
    return _orig_invoke(self, input, **kwargs)


def _on_sigint(signum, frame):
    if _stop.is_set():
        # Ctrl+C lan hai = thoi lich su, chet ngay.
        raise KeyboardInterrupt
    _stop.set()
    print("", flush=True)
    print(
        "[dung] Da nhan Ctrl+C. Cho cac chunk dang goi LLM chay not "
        "(toi da ~90s theo timeout). Phan da xong van nam trong Neo4j va kag/ckpt/.",
        flush=True,
    )
    print(
        "[dung] Chay lai dung lenh cu de tiep tuc. Ctrl+C lan nua de chet ngay.",
        flush=True,
    )


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
