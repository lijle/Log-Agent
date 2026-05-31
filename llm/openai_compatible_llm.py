from __future__ import annotations

import os

from openai import OpenAI

from llm.base_llm import BaseLLM


class OpenAICompatibleLLM(BaseLLM):
    """OpenAI 兼容接口的 LLM 适配器。

    作用：
    - 适配 OpenAI 官方接口风格
    - 也能兼容 DashScope 等提供 OpenAI-compatible API 的服务
    - 给上层提供统一的 `generate` 方法
    """

    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        """初始化真实模型客户端。

        输入：
        - api_key：访问模型服务所需的密钥
        - model：要调用的模型名
        - base_url：可选的兼容接口地址

        输出：
        - None：会在实例上保存 model 和 OpenAI 客户端
        """

        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    @classmethod
    def from_env(cls) -> "OpenAICompatibleLLM | None":
        """从环境变量中构造 LLM 实例。

        作用：
        - 读取 `.env` 或系统环境中的配置
        - 如果没有 API Key，则返回 None，让上层改用 FakeLLM

        输入：
        - 无

        输出：
        - OpenAICompatibleLLM | None：成功则返回实例，否则返回 None
        """

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        base_url = os.getenv("OPENAI_BASE_URL")
        return cls(api_key=api_key, model=model, base_url=base_url)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """调用聊天补全接口生成文本。

        作用：
        - 将 system/user prompt 发送给模型
        - 返回第一条候选回复的文本内容

        输入：
        - system_prompt：系统提示词
        - user_prompt：用户提示词

        输出：
        - str：模型回复内容
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""
