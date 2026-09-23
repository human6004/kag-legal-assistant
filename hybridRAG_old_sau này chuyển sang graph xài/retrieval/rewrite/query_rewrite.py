from llm.prompts import QUERY_REWRITE_PROMPT


class QueryRewrite:

    def __init__(self, llm):
        self.llm = llm

    def rewrite(self, question: str) -> str:
        print("Buoc query rewrite")
        prompt = QUERY_REWRITE_PROMPT.format(
            question=question
        )

        response = self.llm.complete(prompt)

        rewritten_question = response.text.strip()

        return rewritten_question