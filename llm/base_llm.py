from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """LLM 能力的统一抽象接口。

    作用：
    - 屏蔽不同模型提供商的差异
    - 让 ReportTool 只依赖 `generate` 方法，不关心底层实现
    """

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """生成模型回复。

        作用：
        - 接收 system prompt 和 user prompt
        - 返回单条文本结果

        输入：
        - system_prompt：系统角色提示词
        - user_prompt：业务请求提示词

        输出：
        - str：模型生成的文本
        """

        raise NotImplementedError
