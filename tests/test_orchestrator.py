import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import orchestrator


def test_orchestrator_comparison_flow():
    res_state = orchestrator.run(
        session_id="test_sess_123",
        phone_number="27821111111",
        text_message="Please analyze the drilling report and compare it with the latest regulations"
    )

    assert len(res_state["messages"]) > 1
    final_text = res_state["messages"][-1].content
    assert len(final_text) > 0

    report = res_state.get("output_report")
    if report:
        assert "storage_uri" in report


def test_orchestrator_general_interaction():
    res_state = orchestrator.run(
        session_id="test_sess_456",
        phone_number="27821111111",
        text_message="Hello, my name is John."
    )

    assert len(res_state["messages"]) >= 2
    final_text = res_state["messages"][-1].content
    assert len(final_text) > 0


def test_orchestrator_finance_query():
    res_state = orchestrator.run(
        session_id="test_sess_789",
        phone_number="27821111111",
        text_message="Show me the exploration department budget"
    )

    assert len(res_state["messages"]) > 1
    final_text = res_state["messages"][-1].content
    assert len(final_text) > 0


def test_orchestrator_equipment_query():
    res_state = orchestrator.run(
        session_id="test_sess_equip",
        phone_number="27821111111",
        text_message="What is the status of truck TRK-88?"
    )

    assert len(res_state["messages"]) > 1
    final_text = res_state["messages"][-1].content
    assert len(final_text) > 0
