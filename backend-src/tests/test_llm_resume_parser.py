from app.services.llm_resume_parser import LLMResumeParser
from app.services.resume_service import ResumeService


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete(self, *, system_prompt, payload):
        self.calls.append((system_prompt, payload))
        return self.response


def test_llm_resume_parser_accepts_only_verified_known_skills():
    client = FakeClient(
        {
            "name": "Zhang San",
            "skills": [
                {"name": "Python", "evidence": "Python", "confidence": 0.99},
                {"name": "Kubernetes", "evidence": "Kubernetes", "confidence": 0.99},
                {"name": "InventedSkill", "evidence": "InventedSkill", "confidence": 1.0},
            ],
            "experience": [],
            "education": [],
        }
    )
    parser = LLMResumeParser(client=client, enabled=True)
    result = parser.parse("候选人：张三\n技能栈：Python", fallback={"skills": []})

    assert result["llm_used"] is True
    assert result["skills"] == ["Python"]
    assert client.calls[0][1]["schema_version"] == "resume_profile_v1"


def test_llm_resume_parser_falls_back_on_invalid_response():
    fallback = {"name": "local", "skills": ["Python"], "experience": [], "education": []}
    parser = LLMResumeParser(client=FakeClient(["not an object"]), enabled=True)

    result = parser.parse("Python", fallback=fallback)

    assert result["llm_used"] is False
    assert result["skills"] == ["Python"]
    assert "llm_warning" in result


def test_resume_service_supports_explicit_llm_mode(monkeypatch):
    service = ResumeService.__new__(ResumeService)
    service.nlp_service = object()
    service.llm_resume_parser = LLMResumeParser(
        client=FakeClient({"skills": [{"name": "Python", "evidence": "Python"}]}),
        enabled=True,
    )
    monkeypatch.setattr(service, "_parse_with_enhanced", lambda text: {"skills": []})

    result = service.parse_resume_text("Python", mode="llm")

    assert result["llm_used"] is True
    assert result["skills"] == ["Python"]


def test_resume_service_maps_frontend_local_parser_mode(monkeypatch):
    service = ResumeService.__new__(ResumeService)
    service.nlp_service = object()
    service.llm_resume_parser = LLMResumeParser(enabled=False)
    monkeypatch.setattr(
        service,
        "_parse_with_enhanced",
        lambda text: {"name": "local", "skills": ["Python"], "experience": [], "education": []},
    )

    result = service.parse_resume_text("Python", mode="local")

    assert result["skills"] == ["Python"]
