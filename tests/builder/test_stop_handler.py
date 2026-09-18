# -*- coding: utf-8 -*-
"""Chan duy nhat cho co dung o builder/indexer.py.

Chay tu goc repo: .venv/Scripts/python.exe -X utf8 tests/builder/test_stop_handler.py

Co gia tri vi ca ban va nam o mot cho: BuilderComponent.invoke. Upstream doi ten
ham hay doi module la ban va im lang khong lam gi -> test nay gay ngay.
"""
import os
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "kag" / "builder"
sys.path.insert(0, str(BUILDER))
spec = importlib.util.spec_from_file_location(
    "indexer_under_test", BUILDER / "indexer.py"
)
idx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(idx)

from kag.interface.builder.base import BuilderComponent


class _Boom(BuilderComponent):
    def _invoke(self, input, **kwargs):
        raise AssertionError("co dung khong chan duoc _invoke")


class _Ok(BuilderComponent):
    def _invoke(self, input, **kwargs):
        return [input]


def main():
    before = BuilderComponent.invoke
    idx.install_stop_handler()
    assert BuilderComponent.invoke is not before, "khong va duoc invoke"

    assert not idx._stop.is_set()
    idx._on_sigint(2, None)
    assert idx._stop.is_set(), "SIGINT khong bat co"

    # Lan hai chi in goi y taskkill, KHONG duoc nem loi: nem cung khong ep chet
    # duoc (van ket o shutdown(wait=True)), chi lam roi log.
    idx._on_sigint(2, None)
    assert str(os.getpid()) in idx._kill_hint(), "goi y taskkill thieu PID that"

    assert BuilderComponent.invoke(_Boom(), "x") == [], "khong tra ve [] khi da dung"

    idx._stop.clear()

    # --- cau dao: N chunk hong LIEN TIEP thi tu dung ------------------------
    idx._fail_streak = 0
    for i in range(idx._FAIL_LIMIT - 1):
        try:
            BuilderComponent.invoke(_Boom(), "x")
        except AssertionError:
            pass
        assert not idx._stop.is_set(), "dung qua som o lan hong thu %d" % (i + 1)

    # mot chunk chay duoc phai xoa chuoi hong, neu khong thi loi le te cung
    # cham nguong sau vai tram chunk
    BuilderComponent.invoke(_Ok(), "x")
    assert idx._fail_streak == 0, "chunk thanh cong khong reset chuoi hong"

    for _ in range(idx._FAIL_LIMIT):
        try:
            BuilderComponent.invoke(_Boom(), "x")
        except AssertionError:
            pass
    assert idx._stop.is_set(), "hong %d lan lien tiep ma cau dao khong nhay" % idx._FAIL_LIMIT

    idx._stop.clear()
    idx._fail_streak = 0
    print("test_stop_handler: OK")


if __name__ == "__main__":
    main()
