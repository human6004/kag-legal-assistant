import math
import re
import pickle
from pathlib import Path
from typing import List, Dict, Any, Tuple


class BM25OkapiIndex:
    """
    Cài đặt thuật toán Okapi BM25 thuần Python phục vụ Keyword/Sparse Search.
    Hỗ trợ lưu trữ (persist) và nạp lại (load) từ file pickle.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avgdl = 0.0
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}
        self.doc_len: List[int] = []
        self.documents: List[Dict[str, Any]] = []

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tách từ đơn giản qua regex chữ và số tiếng Việt, chuyển chữ thường"""
        # Hỗ trợ ký tự chữ tiếng Việt và ký tự số, ký hiệu văn bản luật (/, -)
        tokens = re.findall(r"[\wĐđ]+", text.lower())
        return tokens

    def fit(self, documents: List[Dict[str, Any]]):
        """
        Huấn luyện/Xây dựng chỉ mục BM25 từ danh sách document.
        Mỗi document là một dict gồm: {"content": str, "metadata": dict}
        """
        self.documents = documents
        self.corpus_size = len(documents)
        if self.corpus_size == 0:
            return

        total_length = 0
        self.doc_len = []
        self.doc_freqs = []
        df_counts: Dict[str, int] = {}

        for doc in documents:
            tokens = self.tokenize(doc["content"])
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

        # Tính IDF: ln((N - n + 0.5) / (n + 0.5) + 1)
        self.idf = {}
        for token, df in df_counts.items():
            self.idf[token] = math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1.0)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """Tìm kiếm các document có điểm BM25 cao nhất đối với câu truy vấn"""
        if self.corpus_size == 0:
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

        # Lấy top_k điểm cao nhất
        scored_docs = [(self.documents[i], scores[i]) for i in range(self.corpus_size) if scores[i] > 0]
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        return scored_docs[:top_k]

    def save(self, filepath: Path | str):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "k1": self.k1,
                "b": self.b,
                "corpus_size": self.corpus_size,
                "avgdl": self.avgdl,
                "doc_freqs": self.doc_freqs,
                "idf": self.idf,
                "doc_len": self.doc_len,
                "documents": self.documents
            }, f)

    @classmethod
    def load(cls, filepath: Path | str) -> "BM25OkapiIndex":
        path = Path(filepath)
        with open(path, "rb") as f:
            data = pickle.load(f)

        instance = cls(k1=data["k1"], b=data["b"])
        instance.corpus_size = data["corpus_size"]
        instance.avgdl = data["avgdl"]
        instance.doc_freqs = data["doc_freqs"]
        instance.idf = data["idf"]
        instance.doc_len = data["doc_len"]
        instance.documents = data["documents"]
        return instance
