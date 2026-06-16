from __future__ import annotations

import json
import re

from agent.react_schema import FINAL_READY_SIGNAL, ReActDecision


THOUGHT_PATTERN = r"Thought:\s*(.*?)(?=\nAction:|\nFinal Answer:|$)"
ACTION_PATTERN = r"Action:\s*([a-zA-Z0-9_]+)"
ACTION_INPUT_PATTERN = r"Action Input:\s*(\{.*\})"
FINAL_ANSWER_PATTERN = r"Final Answer:\s*(.+)"


def parse_react_output(text: str) -> ReActDecision:
    """把 LLM 输出解析成结构化 ReActDecision。

    支持两种文本格式：
    1. 工具调用
       Thought: ...
       Action: rag_tool
       Action Input: {...}
    2. 结束信号
       Thought: ...
       Final Answer: READY_TO_REPORT
    """

    content = text.strip()
    thought = _extract_thought(content)
    final_answer = _extract_final_answer(content)

    if final_answer:
        return ReActDecision(
            thought=thought or "当前证据已经足够，进入最终报告阶段。",
            final_answer=final_answer,
        )

    action = _extract_action(content)
    action_input = _extract_action_input(content)
    return ReActDecision(
        thought=thought or "基于当前证据选择下一步动作。",
        action=action,
        action_input=action_input,
    )


def _extract_thought(text: str) -> str:
    """提取 Thought 段。"""

    match = re.search(THOUGHT_PATTERN, text, flags=re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


def _extract_action(text: str) -> str | None:
    """提取 Action。"""

    match = re.search(ACTION_PATTERN, text)
    if not match:
        return None
    return match.group(1).strip()


def _extract_action_input(text: str) -> dict:
    """提取 Action Input 并尝试解析为 JSON。

    如果 JSON 不合法，先返回空字典，由上层合法性校验兜底。
    """

    match = re.search(ACTION_INPUT_PATTERN, text, flags=re.DOTALL)
    if not match:
        return {}

    raw_json = match.group(1).strip()
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError:
        return {}


def _extract_final_answer(text: str) -> str | None:
    """提取 Final Answer，并仅接受 READY_TO_REPORT。"""

    match = re.search(FINAL_ANSWER_PATTERN, text)
    if not match:
        return None

    value = match.group(1).strip()
    if value == FINAL_READY_SIGNAL:
        return value
    return None
