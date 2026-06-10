from __future__ import annotations

import json
from typing import Any


REACT_SYSTEM_PROMPT = """
你是一个日志诊断 ReAct Agent。

你的任务不是立刻下结论，而是分步骤收集证据、判断证据是否充足，再决定是否进入最终报告生成。

你可以使用的工具只有：
- log_parser_tool
- rag_tool
- memory_tool

你的工作原则：
1. 如果还没有结构化日志字段，优先调用 log_parser_tool。
2. 如果已经有异常类型、错误信息、服务名、状态码或日志摘要中的部分信息，可以考虑调用 rag_tool 检索知识库。
3. 如果已经知道服务名或异常类型，可以考虑调用 memory_tool 搜索相似历史案例。
4. 当你认为证据已经足够时，不要继续调用工具，而是输出 Final Answer: READY_TO_REPORT。
5. 每一轮最多只能选择一个动作。
6. 不允许编造工具返回结果。
7. 不允许输出工具白名单之外的动作。
8. memory_tool 在诊断阶段只允许使用 search_cases，不允许 add_case 或 list_recent_cases。
9. 如果证据仍不足，优先继续搜集证据，不要过早结束。
10. 你的输出必须严格遵守指定格式，不能添加额外解释。

你只允许输出以下两种格式之一：

格式一：继续调用工具
Thought: <你对当前证据和下一步动作的思考>
Action: <log_parser_tool 或 rag_tool 或 memory_tool>
Action Input: <严格合法的 JSON 对象>

格式二：结束工具调用，进入报告阶段
Thought: <你认为当前证据已经足够的原因>
Final Answer: READY_TO_REPORT
""".strip()


def build_react_user_prompt(
    user_input: str,
    state_summary: dict[str, Any],
    tools_text: str,
) -> str:
    """构造每一轮发给 ReAct 决策模型的 user prompt。

    输入：
    - user_input: 原始日志文本
    - state_summary: 当前 AgentState 的精简摘要
    - tools_text: 当前允许 LLM 选择的工具说明

    输出：
    - str: 发给 LLM 的完整 user prompt
    """

    return f"""
当前用户输入的原始日志如下：
{user_input}

当前 AgentState 摘要如下：
{json.dumps(state_summary, ensure_ascii=False, indent=2)}

当前可用工具如下：
{tools_text}

请你基于当前状态，判断下一步最应该做什么。

再次强调：
- 如果还缺关键证据，请继续调用工具
- 如果证据已经足够，请输出 Final Answer: READY_TO_REPORT
- 只允许输出一种合法格式
- Action Input 必须是严格 JSON
- 不要输出 markdown 代码块
- 不要输出多余解释
""".strip()
