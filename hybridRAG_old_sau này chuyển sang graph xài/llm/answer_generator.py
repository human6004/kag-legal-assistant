# from llm.gemini import GeminiLLM
from llm.nvidia import NvidiaNimLLM
from llm.prompts import PROMPT, build_prompt



class AnswerGenerator:

    def __init__(self):
        self.llm = NvidiaNimLLM().get_llm()

    def generate(self, question: str, contexts: str) -> str:

        prompt = build_prompt(
            context=contexts,
            question=question,
        )

        full_prompt = (
            PROMPT
            + "\n\n"
            + prompt
        )

        response= self.llm.complete(full_prompt)
        return response.text 