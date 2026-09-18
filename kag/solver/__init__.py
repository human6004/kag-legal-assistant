# -*- coding: utf-8 -*-
import os
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

# Khởi tạo và gắn chốt chặn an toàn cho mọi nhánh truy vấn đồ thị của Solver
from .relation_adapter import install_safe_guard, SafeRelationAdapter, RelationResolutionStatus

install_safe_guard()
