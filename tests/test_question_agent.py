from datetime import date
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from agents import text2sql


VALID_PLAN = {
    "status": "ready",
    "query_name": "revenue_by_region",
    "start_month": "2024-01-01",
    "end_month": "2024-02-01",
    "reason": "Regional revenue for January 2024.",
}


def answer_prompts(monkeypatch, *answers):
    replies = iter(answers)

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt="": next(replies),
    )


@pytest.fixture
def fake_workflow(tmp_path, monkeypatch):
    """Replace planning and database queries with simulated versions."""

    database_file = tmp_path / "warehouse.duckdb"
    database_file.touch()

    planner = MagicMock(
        return_value=text2sql.QueryPlan.model_validate(VALID_PLAN)
    )

    query = MagicMock(
        return_value=[
            ("North", 1250.50),
            ("South", 3400.00),
        ]
    )

    monkeypatch.setattr(
        text2sql,
        "create_query_plan",
        planner,
    )

    monkeypatch.setattr(
        text2sql,
        "revenue_by_region",
        query,
    )

    return database_file, planner, query


def test_valid_plan_has_correct_dates():
    plan = text2sql.QueryPlan.model_validate(VALID_PLAN)

    assert plan.start_month == date(2024, 1, 1)
    assert plan.end_month == date(2024, 2, 1)


@pytest.mark.parametrize(
    "changes",
    [
        {"start_month": "2024-01-15"},
        {"end_month": "2024-01-01"},
        {"query_name": "arbitrary_sql"},
        {"sql": "DELETE FROM raw_sales"},
    ],
)
def test_invalid_plan_is_rejected(changes):
    with pytest.raises(ValidationError):
        text2sql.QueryPlan.model_validate(
            {**VALID_PLAN, **changes}
        )


def test_cancel_before_sending(
    fake_workflow,
    monkeypatch,
):
    database_file, planner, query = fake_workflow
    answer_prompts(monkeypatch, "CANCEL")

    result = text2sql.run_question(
        "January 2024 revenue by region?",
        database_file,
    )

    assert result == 1
    planner.assert_not_called()
    query.assert_not_called()


def test_cancel_before_query(
    fake_workflow,
    monkeypatch,
):
    database_file, planner, query = fake_workflow
    answer_prompts(monkeypatch, "SEND", "CANCEL")

    result = text2sql.run_question(
        "January 2024 revenue by region?",
        database_file,
    )

    assert result == 1
    planner.assert_called_once()
    query.assert_not_called()


def test_unsupported_question_does_not_execute(
    fake_workflow,
    monkeypatch,
):
    database_file, planner, query = fake_workflow

    planner.return_value = text2sql.QueryPlan(
        status="needs_review",
        query_name=None,
        start_month=None,
        end_month=None,
        reason="This question requests an unsupported metric.",
    )

    answer_prompts(monkeypatch, "SEND")

    result = text2sql.run_question(
        "How many customers did we acquire?",
        database_file,
    )

    assert result == 1
    query.assert_not_called()


def test_approved_plan_runs_fixed_query(
    fake_workflow,
    monkeypatch,
    capsys,
):
    database_file, planner, query = fake_workflow
    answer_prompts(monkeypatch, "SEND", "RUN")

    result = text2sql.run_question(
        "January 2024 revenue by region?",
        database_file,
    )

    captured = capsys.readouterr()

    assert result == 0

    query.assert_called_once_with(
        database_file,
        start_month=date(2024, 1, 1),
        end_month=date(2024, 2, 1),
    )

    assert "Total: $4,650.50" in captured.out