# -*- coding: utf-8 -*-
"""Nạp metadata văn bản (node + cạnh) thẳng vào đồ thị.

Chạy trong thư mục kag/, KHÔNG phải thư mục gốc, sau khi đã `knext schema commit`:
    cd kag
    python builder/metadata_to_graph.py
    python builder/injection.py

Vì sao phải đứng ở kag/: import kag gọi init_env, mà _closest_cfg (conf.py:94) đi
NGƯỢC LÊN cây thư mục để tìm kag_config.yaml. Đứng ở gốc project thì file config
là con chứ không phải tổ tiên, dò lên tận ổ đĩa vẫn không thấy, config rỗng và
injection chết ở dòng KAG_CONFIG.all_config["metadata_inject_chain"].

Chạy lại được nhiều lần: writer ghi đè theo id node nên không sinh bản sao.
"""

import logging
import os

from kag.common.registry import import_modules_from_path
from kag.interface import KAGBuilderChain

logger = logging.getLogger(__name__)


def inject():
    from kag.common.conf import KAG_CONFIG

    chain = KAGBuilderChain.from_config(
        KAG_CONFIG.all_config["metadata_inject_chain"]
    )
    chain.invoke(None)
    logger.info("\n\nĐã nạp metadata văn bản vào đồ thị\n\n")


if __name__ == "__main__":
    import_modules_from_path(os.path.dirname(os.path.abspath(__file__)))
    inject()
