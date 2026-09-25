"""
Shared test setup: every test gets an empty DATA_DIR and no model credentials,
so nothing touches the developer's real settings, inbox, or paid APIs.
"""

import pytest

_ENV_VARS = [
    "LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_TIMEOUT_S",
    "OPENAI_API_KEY", "OPENAI_MODEL", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
    "GROQ_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY", "ADMIN_TOKEN",
    "HUBSPOT_ACCESS_TOKEN", "SLACK_WEBHOOK_URL", "CORS_ORIGINS",
]


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    yield
