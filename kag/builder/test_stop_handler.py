# -*- coding: utf-8 -*-
"""Chan duy nhat cho co dung o builder/indexer.py.

Chay (PowerShell khong co &&, dung dau cham phay): cd kag; ..\.venv\Scripts\python.exe builder\test_stop_handler.py

Co gia tri vi ca ban va nam o mot cho: BuilderComponent.invoke. Upstream doi ten
ham hay doi module la ban va im lang khong lam gi -> test nay gay ngay.
"""
import os
import sys
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "indexer_under_test", os.path.join(os.path.dirname(os.path.abspath(__file__)), "indexer.py")
)
idx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(idx)

from kag.interface.builder.base import BuilderComponent


class _Boom(BuilderComponent):
    def _invoke(self, input, **kwargs):
        raise AssertionError("co dung khong chan duoc _invoke")


def main():
    before = BuilderComponent.invoke
    idx.install_stop_handler()
    assert BuilderComponent.invoke is not before, "khong va duoc invoke"

    assert not idx._stop.is_set()
    idx._on_sigint(2, None)
    assert idx._stop.is_set(), "SIGINT khong bat co"

    assert BuilderComponent.invoke(_Boom(), "x") == [], "khong tra ve [] khi da dung"

    idx._stop.clear()
    print("test_stop_handler: OK")


if __name__ == "__main__":
    main()
