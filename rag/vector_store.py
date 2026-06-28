from __future__ import annotations

from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
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
                    "retriever": "sparse",
                }
            )
        return results


class LocalEmbeddingVectorStore:
    """基于 sentence-transformers 的本地向量检索实现。"""
    def __init__(
        self,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    ) -> None:
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.documents: list[dict[str, Any]] = []
        self.embeddings: np.ndarray | None = None

    def build(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents
        corpus = [doc["content"] for doc in documents]
        if not corpus:
            self.embeddings = None
            return

        self.embeddings = self.model.encode(
            corpus,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

    def search(self, query: str, top_k: int = 4) -> list[dict[str, Any]]:
        if self.embeddings is None or not self.documents:
            return []
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0]
        scores = np.dot(self.embeddings, query_embedding)
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
                    "retriever": "dense",
                }
            )
        return results