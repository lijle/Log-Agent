from __future__ import annotations

from html import escape

import markdown


def build_pending_html(
    task_id: str,
    status: str,
    refresh_seconds: int = 2,
) -> str:
    """构造自动刷新任务状态的等待页面。"""
    safe_task_id = escape(task_id)
    safe_status = escape(status)

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="{refresh_seconds}">
    <title>日志诊断处理中</title>
    <style>
        body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            color: #19211d;
            background: #f4f1ea;
            font-family: "Microsoft YaHei", sans-serif;
        }}
        .card {{
            width: min(620px, calc(100% - 48px));
            padding: 36px;
            background: #fffdf8;
            border: 1px solid #d9d4c8;
            border-radius: 16px;
            box-shadow: 0 18px 50px rgba(25, 33, 29, 0.1);
        }}
        .status {{ color: #c94f2d; font-weight: 700; }}
        code {{ word-break: break-all; }}
    </style>
</head>
<body>
    <main class="card">
        <h1>Agent 正在调查日志</h1>
        <p>任务状态：<span class="status">{safe_status}</span></p>
        <p>Task ID：<code>{safe_task_id}</code></p>
        <p>页面每 {refresh_seconds} 秒自动查询一次，完成后会展示诊断报告。</p>
    </main>
</body>
</html>
""".strip()
def build_report_html(
    service_name: str,
    trace_id: str,
    logql_query: str,
    report_markdown: str,
) -> str:
    """将 Markdown 诊断报告转换成浏览器可读的 HTML。

    输入：
    - service_name: 当前诊断的服务名称
    - trace_id: 当前诊断的 Trace ID
    - logql_query: 实际执行的 LogQL
    - report_markdown: Agent 生成的 Markdown 报告

    输出：
    - 完整 HTML 页面
    """
    safe_service_name = escape(service_name)
    safe_trace_id = escape(trace_id)
    safe_logql_query = escape(logql_query)

    # 先转义模型输出中的原始 HTML，避免报告注入任意标签。
    safe_report_markdown = escape(report_markdown)

    report_html = markdown.markdown(
        safe_report_markdown,
        extensions=[
            "fenced_code",
            "tables",
        ],
    )

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
    <title>日志智能诊断报告</title>

    <style>
        :root {{
            --background: #f4f1ea;
            --surface: #fffdf8;
            --text: #19211d;
            --muted: #667069;
            --accent: #c94f2d;
            --border: #d9d4c8;
            --code: #17201c;
        }}

        body {{
            margin: 0;
            color: var(--text);
            background:
                radial-gradient(
                    circle at top right,
                    #e7d8c5,
                    transparent 35%
                ),
                var(--background);
            font-family:
                "Microsoft YaHei",
                "Noto Sans SC",
                sans-serif;
        }}

        .page {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 40px 24px 80px;
        }}

        .header {{
            margin-bottom: 24px;
            padding: 30px;
            color: #fff;
            background: var(--code);
            border-radius: 16px;
        }}

        .header h1 {{
            margin: 0 0 8px;
            font-size: 30px;
        }}

        .header p {{
            margin: 0;
            color: #bdc9c1;
        }}

        .metadata {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(220px, 1fr));
            gap: 14px;
            margin-bottom: 24px;
        }}

        .metadata-card {{
            padding: 18px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
        }}

        .metadata-label {{
            margin-bottom: 8px;
            color: var(--muted);
            font-size: 13px;
        }}

        .metadata-value {{
            font-family: Consolas, monospace;
            word-break: break-all;
        }}

        .query {{
            margin-bottom: 24px;
            padding: 18px;
            color: #dce7df;
            background: var(--code);
            border-radius: 12px;
            overflow-x: auto;
        }}

        .report {{
            padding: 32px;
            line-height: 1.75;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
        }}

        .report h2 {{
            margin-top: 32px;
            padding-bottom: 8px;
            border-bottom: 2px solid var(--accent);
        }}

        .report code {{
            padding: 2px 6px;
            color: #9f351c;
            background: #f0e7dc;
            border-radius: 4px;
        }}

        .report pre {{
            padding: 18px;
            color: #e8eee9;
            background: var(--code);
            border-radius: 10px;
            overflow-x: auto;
        }}

        .report pre code {{
            padding: 0;
            color: inherit;
            background: transparent;
        }}

        @media (max-width: 640px) {{
            .page {{
                padding: 20px 12px 50px;
            }}

            .header,
            .report {{
                padding: 22px;
            }}
        }}
    </style>
</head>

<body>
    <main class="page">
        <header class="header">
            <h1>日志智能诊断报告</h1>
            <p>
                Loki 多条件检索 · LangGraph 调查流程 ·
                RAG 与历史案例辅助
            </p>
        </header>

        <section class="metadata">
            <div class="metadata-card">
                <div class="metadata-label">服务名称</div>
                <div class="metadata-value">
                    {safe_service_name}
                </div>
            </div>

            <div class="metadata-card">
                <div class="metadata-label">Trace ID</div>
                <div class="metadata-value">
                    {safe_trace_id}
                </div>
            </div>
        </section>

        <section class="query">
            <strong>执行的 LogQL</strong>
            <pre>{safe_logql_query}</pre>
        </section>

        <article class="report">
            {report_html}
        </article>
    </main>
</body>
</html>
""".strip()


def build_error_html(error_message: str) -> str:
    """构造诊断失败页面。"""
    safe_error_message = escape(error_message)

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>诊断失败</title>
</head>
<body style="
    padding: 40px;
    color: #5b2018;
    background: #fff4ef;
    font-family: Microsoft YaHei, sans-serif;
">
    <h1>诊断失败</h1>
    <p>{safe_error_message}</p>
</body>
</html>
""".strip()
