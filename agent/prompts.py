"""Agent 可复用提示词常量。

这份文件当前没有直接接入主流程，但保留了后续扩展 ReAct/LLM 版 Agent 时会用到的提示词模板。
"""

SYSTEM_PROMPT = """
You are a log diagnosis agent.
Use tools to parse logs, retrieve troubleshooting knowledge, search historical memory,
and produce a structured diagnosis report.
Prefer deterministic, evidence-based conclusions.
""".strip()


REACT_FORMAT_PROMPT = """
Follow the ReAct format:
Thought: reason about what to do next
Action: the tool name
Action Input: JSON dict for the tool
Observation: tool result
Final Answer: structured diagnosis result
""".strip()
