from llama_index.llms.ollama import Ollama
from llama_index.core import Settings


class OllamaLLM:

    def __init__(self):

        self.llm = Ollama(
            model="qwen2.5:7b",
            request_timeout=300,
        )

        Settings.llm = self.llm

    def get_llm(self):

        return self.llm