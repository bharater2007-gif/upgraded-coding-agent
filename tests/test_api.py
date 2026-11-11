"""Unit and integration tests for API service layer and endpoints."""

from api.server import (
    handle_approve_task,
    handle_auto_run_task,
    handle_chat,
    handle_create_task,
    handle_get_diff,
    handle_get_logs,
    handle_get_task,
    handle_health,
    handle_step_task,
)


def test_api_health():
    data = handle_health()
    assert data["status"] == "healthy"
    assert "active_llm_provider" in data
    assert "primary_model" in data
    assert data["primary_model"] == "gemini-1.5-flash"
    assert "fallback_status" in data
    assert "python_version" in data


def test_api_chat_endpoint():
    # Test chat without task_id
    status_code, data = handle_chat({"message": "How does the self-healing loop work?"})
    assert status_code == 200
    assert "reply" in data
    assert "reasoning" in data
    assert "self-healing" in data["reply"].lower()

    # Test empty message error
    status_code, err = handle_chat({"message": ""})
    assert status_code == 400
    assert "error" in err


def test_api_task_lifecycle():
    # 1. Create task
    status_code, state = handle_create_task({
        "objective": "Build LRU cache",
        "require_hitl": True,
        "max_iterations": 3,
    })
    assert status_code == 201
    task_id = state["task_id"]
    assert task_id != ""
    assert state["status"] == "PENDING"

    # 2. Get task
    status_code, fetched = handle_get_task(task_id)
    assert status_code == 200
    assert fetched["task_id"] == task_id

    # 3. Step task (PENDING -> PLANNING -> CODING)
    status_code, stepped = handle_step_task(task_id)
    assert status_code == 200
    assert stepped["status"] == "CODING"

    # 4. Auto run to HITL Review Gate
    status_code, auto_state = handle_auto_run_task(task_id)
    assert status_code == 200
    assert auto_state["status"] == "HITL_REVIEW"

    # 5. Check Diff
    status_code, diff = handle_get_diff(task_id)
    assert status_code == 200
    assert isinstance(diff, str)

    # 6. Check Thought Logs
    status_code, logs = handle_get_logs(task_id)
    assert status_code == 200
    assert len(logs["thought_log"]) > 0

    # 7. Approve via HITL Gate
    status_code, approved = handle_approve_task(
        task_id,
        {"action": "APPROVE", "feedback": "Approved by human operator."},
    )
    assert status_code == 200
    assert len(approved["hitl_history"]) >= 1
