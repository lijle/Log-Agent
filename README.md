# log-diagnosis-agent

一个本地可运行的日志诊断 Agent MVP，用于模拟后端故障排查场景。项目强调可讲解、可扩展、可脱离企业内部资源运行，并采用参考 HelloAgents 风格的自建 Agent 框架结构，而不是单文件 Demo。

## 1. 项目背景

在真实的后端排障工作中，工程师通常需要：

- 从大量日志中快速提取关键信息
- 判断错误属于超时、数据库连接、鉴权失败还是代码异常
- 检索过往经验和排障文档
- 输出结构化诊断结论和下一步排查建议

本项目用 mock 日志与通用知识库，构建一个本地可运行的 Log Diagnosis Agent，避免任何公司特定数据、服务名、内部平台或敏感信息。

## 2. 架构设计

项目结构如下：

```text
log-diagnosis-agent/
  app.py
  requirements.txt
  README.md
  .env.example

  agent/
  llm/
  tools/
  memory/
  rag/
  parser/
  data/
  db/
  tests/
```

### 核心模块

- `agent/`: Agent 抽象、状态管理、ReAct 风格主循环
- `tools/`: 工具抽象、注册中心、日志解析、RAG、Memory、报告生成
- `memory/`: SQLite 历史案例存储
- `rag/`: 文档加载、切分、向量化、检索
- `parser/`: 基于正则和启发式的日志结构化解析
- `llm/`: LLM 抽象层，支持 FakeLLM 和 OpenAI-compatible API
- `app.py`: Streamlit UI

## 3. Agent Flow

虽然实现上采用了 MVP 友好的确定性编排，但代码结构保持了 ReAct 风格兼容：

1. `Thought`: 先理解日志中最关键的问题信号
2. `Action`: 调用 `log_parser_tool`
3. `Observation`: 获取结构化字段和日志摘要
4. `Action`: 调用 `rag_tool`
5. `Observation`: 检索相关排障知识
6. `Action`: 调用 `memory_tool`
7. `Observation`: 搜索相似历史案例
8. `Action`: 调用 `report_tool`
9. `Final Answer`: 输出结构化诊断报告并落库

## 4. Tools 说明

### `LogParserTool`

从原始日志中提取：

- timestamp
- log level
- service name
- trace_id / request_id / correlation_id
- exception type
- error message
- HTTP status code

同时生成简短日志摘要。

### `RAGTool`

- 从 `data/knowledge_base/*.md` 加载知识文档
- 进行轻量切分
- 使用本地 TF-IDF 向量检索
- 返回最相关知识片段

说明：为了保证无外部依赖可运行，默认采用本地 TF-IDF 检索；后续可平滑替换为 Chroma / FAISS + Embedding。

### `MemoryTool`

基于 SQLite 存储历史诊断案例，支持：

- `add_case`
- `search_cases`
- `list_recent_cases`

### `ReportTool`

生成 Markdown 诊断报告，包含：

- Problem Summary
- Key Log Evidence
- Extracted Fields
- Possible Root Causes
- Recommended Troubleshooting Steps
- Suggested Queries
- Confidence Score
- Related Historical Cases

若配置了 OpenAI-compatible API，则可调用 LLM 优化报告；否则使用确定性规则生成，保证本地可运行。

## 5. RAG Flow

1. 扫描 `data/knowledge_base` 下 markdown 文件
2. 将文档按段落与长度切分为 chunks
3. 建立 TF-IDF 索引
4. 使用“日志摘要 + 错误字段”作为查询
5. 返回 top-k 相关片段

## 6. Memory Flow

1. Agent 完成诊断后，通过 `memory_tool.add_case` 写入 SQLite
2. 新任务开始时，根据日志摘要和异常信息搜索相似案例
3. UI 侧边栏展示最近案例

存储字段包括：

- `case_id`
- `created_at`
- `raw_log_summary`
- `extracted_fields`
- `diagnosis_summary`
- `root_causes`
- `troubleshooting_steps`

## 7. 环境变量

复制 `.env.example` 为 `.env` 后可选配置：

```bash
cp .env.example .env
```

可选参数：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`

如果未配置，系统自动使用 `FakeLLM` / 规则化报告，不影响运行。

## 8. 安装与运行

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动应用

```bash
streamlit run app.py
```

启动后可：

- 直接粘贴日志
- 上传 `.log` / `.txt`
- 点击内置 mock case 查看样例
- 点击 `Analyze Logs` 生成诊断结果

## 9. 示例输出

下面是一个简化后的诊断报告示例：

```markdown
## Problem Summary
The service `order-service` experienced repeated timeout failures while calling a downstream dependency.

## Key Log Evidence
- `ReadTimeoutException`
- HTTP status code `504`
- same trace id appears across retry attempts

## Possible Root Causes
- downstream service latency spike
- network path instability
- timeout threshold configured too aggressively

## Recommended Troubleshooting Steps
1. check downstream latency and error rate
2. inspect pod restarts and resource pressure
3. verify timeout/retry configuration

## Confidence Score
0.82
```

## 10. 面试讲解重点

这个项目适合从以下角度讲解：

- 为什么不用单文件链式调用，而要拆分 Agent / Tool / Memory / RAG
- 如何设计可扩展的 `BaseTool` 与 `ToolRegistry`
- 为什么 ReAct 结构即使在 MVP 中也值得保留
- 如何在无 LLM Key 情况下提供 deterministic fallback
- 如何把日志解析、知识检索、历史经验召回和报告生成串起来

## 11. 后续可扩展方向

- 接入真实 Embedding + FAISS / Chroma
- 引入多轮对话式 Case 跟进
- 增加 trace 聚合、错误聚类、告警上下文融合
- 支持更多日志格式（JSON logs、multi-line stack trace、Nginx access logs）
- 加入评测集和诊断效果评估
