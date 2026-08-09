import pytest
from datetime import datetime, timedelta, timezone
from local_model.gpu_manager import GPUManager


def test_gpu_manager_mock_lifecycle():
    manager = GPUManager(
        project="test-project",
        zone="us-central1-a",
        instance_name="test-gpu-instance",
        idle_timeout_minutes=1
    )

    assert manager.is_mocked is True
    assert manager.get_status() == "STOPPED"

    started = manager.start_gpu()
    assert started is True
    assert manager.get_status() == "RUNNING"

    healthy = manager.wait_for_health()
    assert healthy is True

    should_stop = manager.check_idle_shutdown()
    assert should_stop is False
    assert manager.get_status() == "RUNNING"

    manager.last_request_time = datetime.now(timezone.utc) - timedelta(minutes=2)
    should_stop = manager.check_idle_shutdown()
    assert should_stop is True
    assert manager.get_status() == "STOPPED"


def test_gpu_manager_adapter_integration():
    from local_model.adapter import LocalLLMAdapter
    from langchain_core.messages import HumanMessage

    adapter = LocalLLMAdapter(use_mock=True)
    assert hasattr(adapter, "_gpu_manager")
    assert adapter._gpu_manager.is_mocked is True

    result = adapter.invoke([HumanMessage(content="Hello")])
    assert result is not None
    assert adapter._gpu_manager.get_status() == "RUNNING"
