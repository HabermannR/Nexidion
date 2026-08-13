import json
from types import SimpleNamespace

import pytest

from agent.agent import TurnDeadlineExceeded, _stream_response, _wall_clock_deadline


class FakeEvent:
    def __init__(self, event_type, response=None, text=None):
        self.type = event_type
        self.response = response
        self.text = text

    def model_dump(self, mode="json"):
        return {"type": self.type, "text": self.text}


class FakeResponses:
    def __init__(self, events):
        self.events = events

    def create(self, **kwargs):
        assert kwargs["stream"] is True
        return iter(self.events)


def test_stream_response_returns_completed_response_and_safe_trace(tmp_path):
    completed = SimpleNamespace(output=["done"])
    client = SimpleNamespace(responses=FakeResponses([
        FakeEvent("response.created"),
        FakeEvent("response.output_text.delta", text="sensitive text"),
        FakeEvent("response.completed", response=completed),
    ]))

    response, count = _stream_response(
        client, {"model": "fake"}, "task-1", 2, str(tmp_path),
        False, 5, lambda _message: None,
    )

    assert response is completed
    assert count == 3
    trace = (tmp_path / "task-1.jsonl").read_text()
    assert "response.output_text.delta" in trace
    assert "sensitive text" not in trace
    assert all("payload" not in json.loads(line) for line in trace.splitlines())


def test_stream_response_can_capture_payloads_explicitly(tmp_path):
    completed = SimpleNamespace(output=[])
    client = SimpleNamespace(responses=FakeResponses([
        FakeEvent("response.output_text.delta", text="captured"),
        FakeEvent("response.completed", response=completed),
    ]))

    _stream_response(
        client, {}, "task-2", 1, str(tmp_path), True, 5,
        lambda _message: None,
    )

    assert "captured" in (tmp_path / "task-2.jsonl").read_text()


def test_wall_clock_deadline_interrupts_work():
    with pytest.raises(TurnDeadlineExceeded):
        with _wall_clock_deadline(0.01):
            while True:
                pass
