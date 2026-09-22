import math
import re
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from llama_index.core.schema import NodeWithScore, TextNode


class BM25Search:
    """
    Module Sparse/Keyword Search sử dụng BM25Okapi cho văn bản pháp luật tiếng Việt.
    Trả về danh sách NodeWithScore tương thích hoàn toàn với LlamaIndex.
    """

    def __init__(
        self,
        nodes: Optional[List[Any]] = None,
        cache_path: str = "./database/bm25_index.pkl",
        k1: float = 1.5,
        b: float = 0.75,
        top_k: int = 5
    ):
        self.k1 = k1
        self.b = b
        self.top_k = top_k
        self.cache_path = Path(cache_path)

        self.corpus_size = 0
        self.avgdl = 0.0
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}
        self.doc_len: List[int] = []
        self.nodes: List[Any] = []

        if nodes is not None and len(nodes) > 0:
            self.fit(nodes)
            self.save()
        elif self.cache_path.exists():
            self.load()
        else:
            # Chưa có nodes và chưa có cache
            pass

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tách từ hỗ trợ tiếng Việt, số hiệu văn bản (13/2023/NĐ-CP), điều khoản."""
        return re.findall(r"[\wĐđ/-]+", text.lower())

    def fit(self, nodes: List[Any]):
        """Xây dựng chỉ mục BM25 từ danh sách LlamaIndex Nodes."""
        self.nodes = nodes
        self.corpus_size = len(nodes)
        if self.corpus_size == 0:
            return

        total_length = 0
        self.doc_len = []
        self.doc_freqs = []
        df_counts: Dict[str, int] = {}

        for node in nodes:
            if hasattr(node, "get_content"):
                text = node.get_content()
            elif hasattr(node, "text"):
                text = node.text
            else:
                text = str(node)

            tokens = self.tokenize(text)
            length = len(tokens)
            self.doc_len.append(length)
            total_length += length

            freq: Dict[str, int] = {}
            for token in tokens:
                freq[token] = freq.get(token, 0) + 1
            self.doc_freqs.append(freq)

            for token in freq.keys():
                df_counts[token] = df_counts.get(token, 0) + 1

        self.avgdl = total_length / self.corpus_size

        # IDF chuẩn Okapi
        self.idf = {}
        for token, df in df_counts.items():
            self.idf[token] = math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1.0)

    def search(self, query: str, top_k: Optional[int] = None) -> List[NodeWithScore]:
        """Tìm kiếm các Node khớp từ khóa BM25 cao nhất."""
        k = top_k if top_k is not None else self.top_k
        if self.corpus_size == 0 or not self.nodes:
            return []

        query_tokens = self.tokenize(query)
        scores = [0.0] * self.corpus_size

        for token in query_tokens:
            if token not in self.idf:
                continue
            token_idf = self.idf[token]

            for i in range(self.corpus_size):
                f = self.doc_freqs[i].get(token, 0)
                if f > 0:
                    numerator = f * (self.k1 + 1)
                    denominator = f + self.k1 * (1 - self.b + self.b * (self.doc_len[i] / self.avgdl))
                    scores[i] += token_idf * (numerator / denominator)

        # Lọc các node có score > 0
        scored_pairs = [
            (self.nodes[i], scores[i])
            for i in range(self.corpus_size)
            if scores[i] > 0
        ]
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        results: List[NodeWithScore] = []
        for node, score in scored_pairs[:k]:
            if isinstance(node, NodeWithScore):
                results.append(NodeWithScore(node=node.node, score=float(score)))
            else:
                results.append(NodeWithScore(node=node, score=float(score)))

        return results

    def save(self, filepath: Optional[Path | str] = None):
        """Lưu trạng thái BM25 ra đĩa."""
        target = Path(filepath) if filepath else self.cache_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as f:
            pickle.dump({
                "k1": self.k1,
                "b": self.b,
                "corpus_size": self.corpus_size,
                "avgdl": self.avgdl,
                "doc_freqs": self.doc_freqs,
                "idf": self.idf,
                "doc_len": self.doc_len,
                "nodes": self.nodes,
            }, f)

    def load(self, filepath: Optional[Path | str] = None):
        """Nạp trạng thái BM25 từ đĩa."""
        target = Path(filepath) if filepath else self.cache_path
        if not target.exists():
            return False
        with open(target, "rb") as f:
            data = pickle.load(f)

        self.k1 = data["k1"]
        self.b = data["b"]
        self.corpus_size = data["corpus_size"]
        self.avgdl = data["avgdl"]
        self.doc_freqs = data["doc_freqs"]
        self.idf = data["idf"]
        self.doc_len = data["doc_len"]
        self.nodes = data["nodes"]
        return True
