from llm.prompts import QUERY_REWRITE_PROMPT


class QueryRewrite:

    def __init__(self, llm):
        self.llm = llm

    def rewrite(self, question: str) -> str:
        print("[PIPELINE] Bước 1: Query Rewrite")
        if self.llm is None:
            return question

        try:
            prompt = QUERY_REWRITE_PROMPT.format(question=question)
            response = self.llm.complete(prompt)
            rewritten_question = response.text.strip()
            if rewritten_question:
                return rewritten_question
        except Exception as e:
            print(f"[CẢNH BÁO] QueryRewrite gặp lỗi LLM ({e}), fallback về câu hỏi gốc.")

        return question