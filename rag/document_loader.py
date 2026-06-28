from __future__ import annotations

from pathlib import Path


def load_markdown_documents(knowledge_base_dir: Path) -> list[dict[str, str]]:
    """读取知识库目录下的 Markdown 文档。

    输入：
    - knowledge_base_dir：知识库目录路径

    输出：
    - list[dict[str, str]]：每个元素包含 source 和 content

    返回类似：
    [
    {
        "source": "database_connection_diagnosis.md",
        "content": "# Database Connection Diagnosis Guide\n..."
    },
    {
        "source": "cloudwatch_log_checklist.md",
        "content": "# CloudWatch-like Log Checklist\n..."
    }
]
    """

    documents: list[dict[str, str]] = []
    for path in sorted(knowledge_base_dir.glob("*.md")):
        documents.append({"source": path.name, "content": path.read_text(encoding="utf-8")})
    return documents


def split_text_with_overlap(text: str, chunk_size: int, overlap: int) -> list[str]:
    """对单段长文本做带 overlap 的字符级兜底切分。"""
    chunks: list[str] = []
    start = 0
    while start<len(text):
        end=min(len(text),start+chunk_size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(end-overlap, start+1)

    return chunks

def split_documents(
    documents: list[dict[str, str]],
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[dict[str, str]]:
    """把长文档优先按段落切分，过长段落再做字符级兜底切分。"""

    chunks: list[dict[str, str]] = []

    for doc in documents:
        content = doc["content"].strip()
        if not content:
            continue

        paragraphs = [item.strip() for item in content.split("\n\n") if item.strip()]

        for paragraph in paragraphs:
            if len(paragraph) <= chunk_size:
                chunks.append(
                    {
                        "source": doc["source"],
                        "content": paragraph,
                    }
                )
                continue

            fallback_chunks = split_text_with_overlap(
                text=paragraph,
                chunk_size=chunk_size,
                overlap=overlap,
            )
            for chunk in fallback_chunks:
                chunks.append(
                    {
                        "source": doc["source"],
                        "content": chunk,
                    }
                )

    return chunks
