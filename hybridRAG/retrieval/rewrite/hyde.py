from llm.prompts import HYDE_PROMPT


class HyDE:

    def __init__(self, llm):
        self.llm = llm

    def generate(self, question: str) -> str:
        print("[PIPELINE] Bước 2: HyDE (Sinh văn bản quy phạm pháp luật giả định)")
        if self.llm is None:
            return question

        try:
            prompt = HYDE_PROMPT.format(question=question)
            response = self.llm.complete(prompt)
            hypothetical_doc = response.text.strip()
            if hypothetical_doc:
                return hypothetical_doc
        except Exception as e:
            print(f"[CẢNH BÁO] HyDE gặp lỗi LLM ({e}), fallback về câu hỏi gốc.")

        return question