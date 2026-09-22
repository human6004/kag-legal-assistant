# llm/nvidia.py (Tương thích ngược, gọi get_default_llm)
from llm.config import get_default_llm


class NvidiaNimLLM:
    """Wrapper tương thích ngược sử dụng LLM được cấu hình trong .env (Gemini qua 9router)."""

    def __init__(self):
        self.llm = get_default_llm()

    def get_llm(self):
        return self.llm


# Alias để gọi theo chuẩn mới
OpenAILikeLLM = NvidiaNimLLM