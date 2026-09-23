# llm/nvidia_nim.py
import os
from dotenv import load_dotenv
from llama_index.llms.openai_like import OpenAILike
from llama_index.core import Settings
from llama_index.core.types import PydanticProgramMode

load_dotenv()


class NvidiaNimLLM:

    def __init__(self):
        self.llm = OpenAILike(
            model="Combomodel",
            api_base="http://localhost:20128/v1",
            api_key=os.getenv("NVIDIA_API_KEY"),
            is_chat_model=True,
            is_function_calling_model=False,
            pydantic_program_mode=PydanticProgramMode.LLM,  # them dong nay
            context_window=16384,
            timeout=60.0,
            max_retries=2,
        )

        Settings.llm = self.llm

    def get_llm(self):
        return self.llm