from __future__ import annotations

from llm.base_llm import BaseLLM


class FakeLLM(BaseLLM):
    """本地回退用的假 LLM。

    作用：
    - 在没有 API Key 时占位
    - 保证项目仍然能本地运行
    - 让上层逻辑继续沿用统一的 LLM 接口
    """

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """返回固定的回退提示文本。

        作用：
        - 告诉上层当前处于无真实模型的回退模式

        输入：
        - system_prompt：未实际使用，仅为了兼容接口
        - user_prompt：未实际使用，仅为了兼容接口

        输出：
        - str：固定说明文本
        """

        return (
            "当前处于 FakeLLM 回退模式。"
            "请根据已提供的证据，使用确定性规则生成诊断报告。"
        )
