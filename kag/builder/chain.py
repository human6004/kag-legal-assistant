# -*- coding: utf-8 -*-
"""Chain không để một chunk hỏng kéo cả văn bản theo.

``DefaultUnstructuredBuilderChain.invoke`` của KAG 0.8.0 gọi thẳng
``inner_future.result()``. Một chunk ném exception là cả lời gọi ``invoke`` nổ
theo, ``runner.py`` đếm văn bản đó là thất bại và KHÔNG ghi checkpoint — nên
mọi chunk tốt còn lại của văn bản phải trích xuất lại từ đầu ở lần chạy sau.
Với 1121 chunk thì đó là tiền gọi LLM thật.

Không chép lại 75 dòng ``invoke`` của lớp cha. Bọc ``invoke`` của từng node lại
là đủ: node nào hỏng thì trả rỗng, future không bao giờ ném, lớp cha chạy như
thường.

Thứ tự bọc có ý nghĩa. ``indexer.py`` thay ``BuilderComponent.invoke`` bằng
``_invoke_with_stop`` để đếm số chunk hỏng liên tiếp và ngắt build khi gateway
hoặc quota chết. Lớp bọc ở đây nằm NGOÀI lớp đó, nên cầu dao vẫn đếm được lỗi
trước khi lỗi bị nuốt. Nuốt exception ở trong ``extractor._invoke`` thì cầu dao
mù, build hết quota sẽ quay không tải hàng tiếng.
"""

import logging

from kag.interface import KAGBuilderChain
from kag.builder.default_chain import DefaultUnstructuredBuilderChain

logger = logging.getLogger(__name__)

_WRAPPED = "_legal_skip_on_error"


@KAGBuilderChain.register("legal_unstructured_builder_chain")
class LegalUnstructuredBuilderChain(DefaultUnstructuredBuilderChain):
    def invoke(self, input_data, max_workers=10, **kwargs):
        for name in ("extractor", "vectorizer", "post_processor", "writer"):
            node = getattr(self, name, None)
            if node is None or getattr(node, _WRAPPED, False):
                continue
            setattr(node, "invoke", self._skip_on_error(node.invoke, name))
            setattr(node, _WRAPPED, True)
        return super().invoke(input_data, max_workers=max_workers, **kwargs)

    @staticmethod
    def _skip_on_error(inner, name):
        # ponytail: bỏ nguyên chunk khi một node hỏng, không thử lại node sau.
        # Retry đã có sẵn ở tầng dưới (@retry của tenacity trong extractor).
        # Cần tinh hơn thì viết lại invoke của lớp cha cho chạy tiếp từng node.
        def safe(*args, **kwargs):
            try:
                return inner(*args, **kwargs)
            except Exception:
                logger.exception("Node %s hỏng ở một chunk, bỏ qua chunk này.", name)
                return []

        return safe
