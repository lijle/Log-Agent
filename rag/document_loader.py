from __future__ import annotations

from pathlib import Path


def load_markdown_documents(knowledge_base_dir: Path) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    for path in sorted(knowledge_base_dir.glob("*.md")):
        documents.append({"source": path.name, "content": path.read_text(encoding="utf-8")})
    return documents


def split_documents(
    documents: list[dict[str, str]],
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for doc in documents:
        content = doc["content"].strip()
        if not content:
            continue
        start = 0
        while start < len(content):
            end = min(len(content), start + chunk_size)
            chunk = content[start:end]
            chunks.append({"source": doc["source"], "content": chunk})
            if end == len(content):
                break
            start = max(end - overlap, start + 1)
    return chunks
