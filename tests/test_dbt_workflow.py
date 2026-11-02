import pytest

from graphs import main_graph


@pytest.fixture
def fake_nodes(monkeypatch):
    """Simulate workflow nodes without databases or API requests."""

    calls = []

    def ingestion(state):
        calls.append("ingestion")
        return {
            "current_agent": "IngestionAgent",
            "cleaned_records": [{"example": "test record"}],
        }

    def warehouse(state):
        calls.append("warehouse")
        return {"current_agent": "WarehouseAgent"}

    def dbt(state):
        calls.append("dbt")
        return {
            "current_agent": "DbtAgent",
            "dbt_success": True,
        }

    monkeypatch.setattr(main_graph, "ingestion_node", ingestion)
    monkeypatch.setattr(main_graph, "warehouse_node", warehouse)
    monkeypatch.setattr(main_graph, "dbt_node", dbt)

    return calls


def starting_state():
    return {
        "messages": [],
        "intent": "full_pipeline",
        "cleaned_records": None,
        "artifacts": {},
    }


@pytest.mark.parametrize("include_dbt", [False, True])
def test_dbt_is_explicitly_requested(fake_nodes, include_dbt):
    result = main_graph.build_graph(
        include_dbt=include_dbt
    ).invoke(starting_state())

    if include_dbt:
        assert fake_nodes == ["ingestion", "warehouse", "dbt"]
        assert result["dbt_success"] is True
    else:
        assert fake_nodes == ["ingestion", "warehouse"]
        assert result["current_agent"] == "WarehouseAgent"


def test_cancellation_skips_warehouse_and_dbt(
    fake_nodes,
    monkeypatch,
):
    def cancelled(state):
        fake_nodes.append("ingestion")
        return {"cleaned_records": None}

    monkeypatch.setattr(
        main_graph,
        "ingestion_node",
        cancelled,
    )

    result = main_graph.build_graph(
        include_dbt=True
    ).invoke(starting_state())

    assert result["cleaned_records"] is None
    assert fake_nodes == ["ingestion"]


def test_dbt_failure_stops_workflow(fake_nodes, monkeypatch):
    def failed_dbt(state):
        raise RuntimeError("Simulated dbt failure.")

    monkeypatch.setattr(
        main_graph,
        "dbt_node",
        failed_dbt,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated dbt failure",
    ):
        main_graph.build_graph(
            include_dbt=True
        ).invoke(starting_state())