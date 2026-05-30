from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class LocalTfidfVectorStore:
    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.documents: list[dict[str, Any]] = []
        self.matrix = None

    def build(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents
        corpus = [doc["content"] for doc in documents]
        self.matrix = self.vectorizer.fit_transform(corpus) if corpus else None

    def search(self, query: str, top_k: int = 4) -> list[dict[str, Any]]:
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
