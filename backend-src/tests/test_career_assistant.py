import json

from app.services import career_assistant_service as service


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps({
            "model": "deepseek-chat",
            "choices": [{"message": {"content": "先补齐SQL，再完成一个可展示的数据项目。"}}],
        }).encode("utf-8")


def test_assistant_uses_bounded_history_and_page_context(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(service.settings, "CAREER_ASSISTANT_API_KEY", "test-key")
    monkeypatch.setattr(service.urllib.request, "urlopen", fake_urlopen)
    history = [{"role": "user", "content": f"问题{i}"} for i in range(12)]
    result = service.ask_career_assistant("下一步做什么？", history, {"page": "人岗诊断"})

    assert result["available"] is True
    assert "SQL" in result["answer"]
    assert captured["body"]["messages"][-1]["content"] == "下一步做什么？"
    assert len([m for m in captured["body"]["messages"] if m["role"] == "user"]) == 9
    assert "人岗诊断" in captured["body"]["messages"][1]["content"]


def test_assistant_returns_configuration_message_without_key(monkeypatch):
    monkeypatch.setattr(service.settings, "CAREER_ASSISTANT_API_KEY", None)
    monkeypatch.setattr(service.settings, "DEEPSEEK_API_KEY", None)
    result = service.ask_career_assistant("你好")
    assert result["available"] is False
    assert "配置" in result["answer"]
