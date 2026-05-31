from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class LocalTfidfVectorStore:
    """基于 TF-IDF 的本地轻量向量检索实现。

    作用：
    - 用 scikit-learn 将知识片段向量化
    - 用余弦相似度完成文本检索
    - 作为无外部依赖的 RAG fallback
    """

    def __init__(self) -> None:
        """初始化向量化器和内部状态。

        输出：
        - None
        """

        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.documents: list[dict[str, Any]] = []
        self.matrix = None

    def build(self, documents: list[dict[str, Any]]) -> None:
        """根据知识片段建立 TF-IDF 矩阵。

        输入：
        - documents：切分后的知识片段列表

        输出：
        - None：内部会保存原始文档和向量矩阵
        """

        self.documents = documents
        corpus = [doc["content"] for doc in documents]
        self.matrix = self.vectorizer.fit_transform(corpus) if corpus else None

    def search(self, query: str, top_k: int = 4) -> list[dict[str, Any]]:
        """检索与查询最接近的知识片段。

        输入：
        - query：查询文本
        - top_k：最多返回多少条结果

        输出：
        - list[dict[str, Any]]：包含 source、content、score 的结果列表
        """

        if self.matrix is None or not self.documents:
            return []
        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self.matrix).flatten()
        ranked_indices = scores.argsort()[::-1][:top_k]
        results: list[dict[str, Any]] = []
        for idx in ranked_indices:
            score = float(scores[idx])
            if score <= 0:
                continue
            doc = self.documents[idx]
            results.append(
                {
                    "source": doc["source"],
                    "content": doc["content"],
                    "score": score,
                }
            )
        return results
