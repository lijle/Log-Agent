from agent.react_parser import parse_react_output
from agent.react_schema import FINAL_READY_SIGNAL


def test_parse_react_output_action() -> None:
    text = """
Thought: 当前已经拿到异常类型和错误信息，下一步检索知识库。
Action: rag_tool
Action Input: {"query": "timeout 504", "top_k": 4}
""".strip()

    decision = parse_react_output(text)

    assert decision.thought.startswith("当前已经拿到异常类型")
    assert decision.action == "rag_tool"
    assert decision.action_input["query"] == "timeout 504"
    assert decision.is_final is False


def test_parse_react_output_final() -> None:
    text = """
Thought: 当前证据已经足够，进入最终报告阶段。
Final Answer: READY_TO_REPORT
""".strip()

    decision = parse_react_output(text)

    assert decision.final_answer == FINAL_READY_SIGNAL
    assert decision.is_final is True
