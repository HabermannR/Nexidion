import pytest

from backend.services import llm_provider


class FakeOpenAI:
    calls = []

    def __init__(self, **kwargs):
        self.calls.append(kwargs)


@pytest.fixture(autouse=True)
def clean_provider_environment(monkeypatch):
    for name in (
        "LOCAL_LLM_URL", "LOCAL_LLM_API_KEY", "LOCAL_LLM_MODEL",
        "OPENAI_API_KEY", "OPENAI_MODEL", "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL", "OPENROUTER_HTTP_REFERER", "OPENROUTER_APP_TITLE",
    ):
        monkeypatch.delenv(name, raising=False)
    FakeOpenAI.calls.clear()
    monkeypatch.setattr(llm_provider, "OpenAI", FakeOpenAI)


def test_openrouter_uses_compatible_endpoint_and_optional_headers(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model:free")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://nexidion.example")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Nexidion")

    _, model = llm_provider.client_and_model("openrouter")

    assert model == "vendor/model:free"
    assert FakeOpenAI.calls == [{
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "private-key",
        "default_headers": {
            "HTTP-Referer": "https://nexidion.example",
            "X-Title": "Nexidion",
        },
    }]


def test_openrouter_requested_model_does_not_require_default(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-key")
    _, model = llm_provider.client_and_model("openrouter", "another/model:free")
    assert model == "another/model:free"


def test_openrouter_requires_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY is not configured"):
        llm_provider.client_and_model("openrouter")


def test_openrouter_requires_explicit_or_configured_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-key")
    with pytest.raises(ValueError, match="OPENROUTER_MODEL is not configured"):
        llm_provider.client_and_model("openrouter")


def test_unsupported_provider_is_rejected():
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        llm_provider.client_and_model("unknown")
