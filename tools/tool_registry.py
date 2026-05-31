from __future__ import annotations

from tools.base_tool import BaseTool


class ToolRegistry:
    """工具注册中心。

    作用：
    - 统一保存所有可用工具
    - 提供按名称获取工具的能力
    - 供 Agent 在运行时动态查找和调用工具
    """

    def __init__(self) -> None:
        """初始化内部工具字典。

        输入：
        - 无

        输出：
        - None：创建空的工具映射表
        """

        self._tools: dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """注册一个工具实例。

        输入：
        - tool：实现了 BaseTool 接口的工具对象

        输出：
        - None：工具会以 `tool.name` 为键保存到注册表
        """

        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        """根据名称获取工具。

        输入：
        - name：工具名，比如 `log_parser_tool`

        输出：
        - BaseTool：对应的工具实例；若不存在则抛出 KeyError
        """

        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    def list_tools(self) -> list[str]:
        """列出当前已注册的工具名。

        输出：
        - list[str]：工具名列表
        """

        return list(self._tools.keys())

    def format_tools_for_prompt(self) -> str:
        """将工具清单格式化为提示词文本。

        作用：
        - 在需要让 LLM 知道有哪些工具可用时，生成易读的说明文本

        输出：
        - str：每行一个工具描述的字符串
        """

        return "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self._tools.values()
        )
