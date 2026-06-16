from pathlib import Path

from dotenv import load_dotenv

from agent.langgraph_agent import LangGraphAgent


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    raw_log = (PROJECT_ROOT / "data" / "mock_logs" / "db_connection_case.log").read_text(
        encoding="utf-8"
    )

    result = LangGraphAgent().run(raw_log)

    print(result["report_markdown"][:500])
    print("trace length =", len(result["trace"]))
    print("decision_source =", result.get("decision_source"))
    print("llm_raw_output =", result.get("llm_raw_output"))
    print("report_llm_source =", result.get("report_llm_source"))


if __name__ == "__main__":
    main()