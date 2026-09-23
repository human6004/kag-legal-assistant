from sentence_transformers import CrossEncoder
from typing import List

class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", top_k: int = 5):
        self.top_k = top_k
        self.model = CrossEncoder(model_name, max_length=512)

    def rerank(self, question: str, nodes: List) -> List:
        if not nodes:
            return []

        pairs = [[question, node.text] for node in nodes]
        scores = self.model.predict(pairs)

        ranked = sorted(zip(nodes, scores), key=lambda x: x[1], reverse=True)

        for node, score in ranked:
            node.score = float(score)

        return [node for node, _ in ranked[:self.top_k]]