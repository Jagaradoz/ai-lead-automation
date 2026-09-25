"""
test_settings_store.py
Unit tests for model settings: env defaults, persistence, key masking, provider factory.
"""

import json

import pytest
from pydantic import ValidationError

from scripts.llm.providers import AnthropicProvider, OpenAICompatibleProvider
from scripts.llm.settings_store import (
    PRESETS,
    ModelSettings,
    ModelSettingsUpdate,
    SettingsStore,
    build_provider,
    public_view,
)


def test_defaults_to_rules_only_without_env(tmp_path):
    settings = SettingsStore(tmp_path / "settings.json", env={}).load()
    assert settings.provider == "none"
    assert settings.is_configured is False


def test_env_defaults_use_llm_variables(tmp_path):
    env = {"LLM_PROVIDER": "groq", "LLM_MODEL": "llama-x", "LLM_API_KEY": "gsk_abc"}
    settings = SettingsStore(tmp_path / "s.json", env=env).load()
    assert settings.provider == "groq"
    assert settings.base_url == PRESETS["groq"].base_url
    assert settings.model == "llama-x"
    assert settings.api_key == "gsk_abc"
    assert settings.is_configured is True


def test_legacy_openai_env_is_honoured(tmp_path):
    env = {"OPENAI_API_KEY": "sk-legacy", "OPENAI_MODEL": "gpt-4o-mini"}
    settings = SettingsStore(tmp_path / "s.json", env=env).load()
    assert settings.provider == "openai"
    assert settings.model == "gpt-4o-mini"
    assert settings.api_key == "sk-legacy"


def test_placeholder_openai_key_is_ignored(tmp_path):
    env = {"OPENAI_API_KEY": "your_openai_api_key_here"}
    assert SettingsStore(tmp_path / "s.json", env=env).load().provider == "none"


def test_save_round_trip_and_file_overrides_env(tmp_path):
    path = tmp_path / "s.json"
    store = SettingsStore(path, env={"LLM_PROVIDER": "openai", "LLM_MODEL": "a", "LLM_API_KEY": "sk-env"})
    saved = store.save(ModelSettingsUpdate(provider="ollama", model="llama3.1", base_url="http://localhost:11434/v1"))

    assert saved.provider == "ollama"
    assert store.load() == saved
    assert json.loads(path.read_text(encoding="utf-8"))["model"] == "llama3.1"


def test_api_key_keep_replace_remove(tmp_path):
    store = SettingsStore(tmp_path / "s.json", env={})
    store.save(ModelSettingsUpdate(provider="openai", model="m", api_key="sk-first-1234"))

    kept = store.save(ModelSettingsUpdate(model="m2"))
    assert kept.api_key == "sk-first-1234"

    replaced = store.save(ModelSettingsUpdate(api_key="sk-second-9876"))
    assert replaced.api_key == "sk-second-9876"

    removed = store.save(ModelSettingsUpdate(api_key=""))
    assert removed.api_key == ""
    assert removed.is_configured is False


def test_unset_key_in_file_falls_back_to_env_key(tmp_path):
    store = SettingsStore(tmp_path / "s.json", env={"ANTHROPIC_API_KEY": "sk-ant-env"})
    saved = store.save(ModelSettingsUpdate(provider="anthropic", model="claude-opus-5"))
    assert saved.api_key == "sk-ant-env"


def test_public_view_never_exposes_key():
    settings = ModelSettings(provider="openai", base_url="https://api.openai.com/v1", model="m", api_key="sk-supersecret-4f2a")
    view = public_view(settings)
    assert "sk-supersecret-4f2a" not in json.dumps(view)
    assert view["has_api_key"] is True
    assert view["api_key_hint"].endswith("4f2a")


def test_rejects_unknown_provider_and_bad_timeout():
    with pytest.raises(ValidationError):
        ModelSettings(provider="skynet")
    with pytest.raises(ValidationError):
        ModelSettings(provider="openai", timeout_s=0)


def test_keyless_local_provider_is_configured_without_key():
    settings = ModelSettings(provider="ollama", base_url="http://localhost:11434/v1", model="llama3.1")
    assert settings.is_configured is True


def test_build_provider_picks_adapter():
    openai_like = ModelSettings(provider="openrouter", base_url="https://openrouter.ai/api/v1", model="x", api_key="k")
    assert isinstance(build_provider(openai_like), OpenAICompatibleProvider)

    claude = ModelSettings(provider="anthropic", model="claude-opus-5", api_key="k")
    assert isinstance(build_provider(claude, anthropic_client=object()), AnthropicProvider)

    with pytest.raises(ValueError):
        build_provider(ModelSettings())


def test_changing_base_url_drops_saved_key(tmp_path):
    store = SettingsStore(tmp_path / "s.json", env={})
    store.save(ModelSettingsUpdate(provider="openai", model="m", api_key="sk-real-key-1234"))

    moved = store.preview(ModelSettingsUpdate(base_url="https://evil.example/v1"))
    assert moved.api_key == ""
    assert moved.is_configured is False

    # Supplying a key together with the new URL is allowed
    explicit = store.preview(ModelSettingsUpdate(base_url="https://proxy.example/v1", api_key="sk-proxy"))
    assert explicit.api_key == "sk-proxy"


def test_env_key_is_not_sent_to_a_foreign_base_url(tmp_path):
    store = SettingsStore(tmp_path / "s.json", env={"OPENROUTER_API_KEY": "sk-or-env"})
    hijack = store.preview(ModelSettingsUpdate(provider="openrouter", model="x", base_url="https://evil.example/v1"))
    assert hijack.api_key == ""

    normal = store.preview(ModelSettingsUpdate(provider="openrouter", model="x"))
    assert normal.api_key == "sk-or-env"


def test_env_base_url_set_by_operator_keeps_env_key(tmp_path):
    env = {"LLM_PROVIDER": "custom", "LLM_BASE_URL": "https://vllm.internal/v1", "LLM_MODEL": "m", "LLM_API_KEY": "k-env"}
    assert SettingsStore(tmp_path / "s.json", env=env).load().api_key == "k-env"
