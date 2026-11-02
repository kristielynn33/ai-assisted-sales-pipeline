from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Describe the shared information passed between agents."""

    messages: Annotated[list[BaseMessage], add_messages]

    intent: Literal["ingest", "query", "full_pipeline"]
    current_agent: str

    # Project 1: Ingestion.
    raw_file_path: str | None
    raw_content: str | None
    cleaned_records: list[dict[str, Any]] | None
    validation_errors: list[str]
    retry_count: int
    force_ai: bool
    review_headers: bool
    anomaly_reason: str | None

    # Project 2: Data warehouse.
    table_name: str | None
    dbt_success: bool | None
    dbt_log: str | None

    # Project 3: Text-to-SQL.
    user_question: str | None
    generated_sql: str | None
    query_result_json: str | None

    # Supporting information.
    memory_hits: list[str]
    reconciliation: dict[str, Any] | None
    artifacts: dict[str, Any]