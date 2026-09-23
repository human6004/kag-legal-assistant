from llm.prompts import HYDE_PROMPT


class HyDE:

    def __init__(self, llm):
        self.llm = llm

    def generate(self, question: str) -> str:
        print("Buoc hyde (cau hoi gia dinh)")
        prompt = HYDE_PROMPT.format(
            question=question
        )

        response = self.llm.complete(prompt)

        return response.text.strip()