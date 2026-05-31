from __future__ import annotations

from pathlib import Path


def load_markdown_documents(knowledge_base_dir: Path) -> list[dict[str, str]]:
    """读取知识库目录下的 Markdown 文档。

    输入：
    - knowledge_base_dir：知识库目录路径

    输出：
    - list[dict[str, str]]：每个元素包含 source 和 content
    """

    documents: list[dict[str, str]] = []
    for path in sorted(knowledge_base_dir.glob("*.md")):
        documents.append({"source": path.name, "content": path.read_text(encoding="utf-8")})
    return documents


def split_documents(
    documents: list[dict[str, str]],
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[dict[str, str]]:
    """把长文档切成较短的知识片段。

    作用：
    - 让后续 TF-IDF 检索粒度更细
    - 通过 overlap 保留片段上下文连续性

    输入：
    - documents：原始文档列表
    - chunk_size：单个片段的最大字符数
    - overlap：相邻片段之间的重叠字符数

    输出：
    - list[dict[str, str]]：切分后的片段列表
    """

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
