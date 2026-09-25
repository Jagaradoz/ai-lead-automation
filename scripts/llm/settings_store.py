"""
settings_store.py
Model settings: provider presets, validation, persistence and the provider factory.

Resolution order:
1. data/settings.json when it exists (written by the Settings page),
2. otherwise environment variables (LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL, LLM_API_KEY,
   plus the legacy OPENAI_API_KEY / OPENAI_MODEL).
An API key left unset in the file falls back to the provider's environment variable,
so keys can stay in .env while everything else is managed in the UI.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scripts.llm.providers import AnthropicProvider, OpenAICompatibleProvider
from scripts.paths import data_dir

KEY_HINT_LENGTH = 4


@dataclass(frozen=True)
class ProviderPreset:
    label: str
    kind: Literal["none", "openai", "anthropic"]
    base_url: str
    key_required: bool
    key_env: Optional[str]
    model_hint: str


PRESETS: Dict[str, ProviderPreset] = {
    "none": ProviderPreset("No model (rules only)", "none", "", False, None, ""),
    "anthropic": ProviderPreset("Anthropic", "anthropic", "https://api.anthropic.com", True, "ANTHROPIC_API_KEY", "claude-opus-5"),
    "openai": ProviderPreset("OpenAI", "openai", "https://api.openai.com/v1", True, "OPENAI_API_KEY", "gpt-4o-mini"),
    "openrouter": ProviderPreset("OpenRouter", "openai", "https://openrouter.ai/api/v1", True, "OPENROUTER_API_KEY", ""),
    "groq": ProviderPreset("Groq", "openai", "https://api.groq.com/openai/v1", True, "GROQ_API_KEY", ""),
    "deepseek": ProviderPreset("DeepSeek", "openai", "https://api.deepseek.com/v1", True, "DEEPSEEK_API_KEY", "deepseek-chat"),
    "gemini": ProviderPreset("Google Gemini", "openai", "https://generativelanguage.googleapis.com/v1beta/openai", True, "GEMINI_API_KEY", ""),
    "ollama": ProviderPreset("Ollama (local)", "openai", "http://localhost:11434/v1", False, None, ""),
    "lmstudio": ProviderPreset("LM Studio (local)", "openai", "http://localhost:1234/v1", False, None, ""),
    "custom": ProviderPreset("Other OpenAI-compatible server", "openai", "", False, None, ""),
}


def _is_placeholder(value: Optional[str]) -> bool:
    return not value or (value.startswith("your_") and value.endswith("_here"))


class ModelSettings(BaseModel):
    model_config = ConfigDict(frozen=True, protected_namespaces=())

    provider: str = "none"
    base_url: str = Field("", max_length=500)
    model: str = Field("", max_length=200)
    api_key: str = Field("", max_length=500, repr=False)
    timeout_s: float = Field(60, ge=5, le=300)
    on_failure: Literal["fallback", "error"] = "fallback"
    extra_instructions: str = Field("", max_length=4000)

    @field_validator("provider")
    @classmethod
    def _known_provider(cls, value: str) -> str:
        if value not in PRESETS:
            raise ValueError(f"Unknown provider '{value}'.")
        return value

    @field_validator("base_url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        value = value.strip()
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return value

    @property
    def preset(self) -> ProviderPreset:
        return PRESETS[self.provider]

    @property
    def is_configured(self) -> bool:
        preset = self.preset
        if preset.kind == "none" or not self.model:
            return False
        if preset.kind == "openai" and not self.base_url:
            return False
        return bool(self.api_key) or not preset.key_required

    def describe(self) -> str:
        if not self.is_configured:
            return "Rules only"
        return f"{self.model} via {self.preset.label}"


class ModelSettingsUpdate(BaseModel):
    """Partial update. For api_key: omitted keeps the stored key, "" removes it."""

    model_config = ConfigDict(protected_namespaces=())

    provider: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = Field(None, max_length=500)
    timeout_s: Optional[float] = None
    on_failure: Optional[Literal["fallback", "error"]] = None
    extra_instructions: Optional[str] = None


class SettingsStore:
    def __init__(self, path: Optional[Path] = None, env: Optional[Mapping[str, str]] = None):
        self._path = path or data_dir() / "settings.json"
        self._env = os.environ if env is None else env

    def _env_key(self, provider: str, base_url: str) -> str:
        """Env keys are only released to the provider's own URL or the operator's LLM_BASE_URL."""
        preset = PRESETS.get(provider)
        trusted = {u.rstrip("/") for u in (preset.base_url if preset else "", self._env.get("LLM_BASE_URL") or "") if u}
        if base_url.rstrip("/") not in trusted and not (provider == "anthropic" and not base_url):
            return ""
        if self._env.get("LLM_PROVIDER") == provider and not _is_placeholder(self._env.get("LLM_API_KEY")):
            return self._env["LLM_API_KEY"]
        key_env = PRESETS[provider].key_env if provider in PRESETS else None
        value = self._env.get(key_env) if key_env else None
        return "" if _is_placeholder(value) else value

    def _from_env(self) -> Dict[str, Any]:
        provider = self._env.get("LLM_PROVIDER")
        if not provider and not _is_placeholder(self._env.get("OPENAI_API_KEY")):
            provider = "openai"
        provider = provider if provider in PRESETS else "none"
        preset = PRESETS[provider]
        model = self._env.get("LLM_MODEL") or (self._env.get("OPENAI_MODEL") if provider == "openai" else None)
        raw: Dict[str, Any] = {
            "provider": provider,
            "base_url": self._env.get("LLM_BASE_URL") or preset.base_url,
            "model": model or preset.model_hint,
            "api_key": None,
        }
        if self._env.get("LLM_TIMEOUT_S"):
            raw["timeout_s"] = float(self._env["LLM_TIMEOUT_S"])
        return raw

    def _read_raw(self) -> Optional[Dict[str, Any]]:
        if not self._path.exists():
            return None
        with open(self._path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _resolve(self, raw: Dict[str, Any]) -> ModelSettings:
        key = raw.get("api_key")
        if key is None:
            key = self._env_key(raw.get("provider", "none"), raw.get("base_url") or "")
        return ModelSettings(**{**raw, "api_key": key or ""})

    def load(self) -> ModelSettings:
        raw = self._read_raw()
        return self._resolve(raw if raw is not None else self._from_env())

    def preview(self, update: ModelSettingsUpdate) -> ModelSettings:
        """Resolves what `update` would produce, without writing it (used by Test connection)."""
        return self._resolve(self._merge(update))

    def save(self, update: ModelSettingsUpdate) -> ModelSettings:
        raw = self._merge(update)
        resolved = self._resolve(raw)  # validates before anything is written
        self._write(raw)
        return resolved

    def _merge(self, update: ModelSettingsUpdate) -> Dict[str, Any]:
        current = self._read_raw() or self._from_env()
        changes = update.model_dump(exclude_unset=True, exclude_none=True)
        if "api_key" in update.model_fields_set and update.api_key is not None:
            changes["api_key"] = update.api_key.strip()

        new_provider = changes.get("provider", current.get("provider", "none"))
        if new_provider != current.get("provider"):
            preset = PRESETS.get(new_provider)
            changes.setdefault("base_url", preset.base_url if preset else "")
            changes.setdefault("model", preset.model_hint if preset else "")
            changes.setdefault("api_key", None)

        # A stored key never follows the request to a different server.
        current_url = (current.get("base_url") or "").rstrip("/")
        new_url = (changes.get("base_url", current.get("base_url")) or "").rstrip("/")
        if new_url != current_url and "api_key" not in changes:
            changes["api_key"] = None

        return {**current, **changes}

    def _write(self, raw: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        # Owner-only from the moment it exists (the mode is ignored on Windows, where ACLs apply).
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._path)


def public_view(settings: ModelSettings) -> Dict[str, Any]:
    """Settings as the browser may see them: the API key is reduced to a hint."""
    data = settings.model_dump(exclude={"api_key"})
    key = settings.api_key
    data.update(
        {
            "has_api_key": bool(key),
            "api_key_hint": f"…{key[-KEY_HINT_LENGTH:]}" if len(key) > KEY_HINT_LENGTH * 2 else ("set" if key else ""),
            "is_configured": settings.is_configured,
            "description": settings.describe(),
            "kind": settings.preset.kind,
        }
    )
    return data


def presets_view() -> list:
    return [
        {
            "id": pid,
            "label": p.label,
            "kind": p.kind,
            "base_url": p.base_url,
            "key_required": p.key_required,
            "model_hint": p.model_hint,
        }
        for pid, p in PRESETS.items()
    ]


def build_provider(settings: ModelSettings, *, transport=None, anthropic_client=None):
    """Creates the adapter for `settings`. Raises ValueError when no model is configured."""
    if not settings.is_configured:
        raise ValueError("No model is configured.")
    if settings.preset.kind == "anthropic":
        base_url = settings.base_url if settings.base_url and settings.base_url != PRESETS["anthropic"].base_url else None
        return AnthropicProvider(
            api_key=settings.api_key,
            model=settings.model,
            timeout_s=settings.timeout_s,
            base_url=base_url,
            client=anthropic_client,
        )
    return OpenAICompatibleProvider(
        base_url=settings.base_url,
        api_key=settings.api_key or None,
        model=settings.model,
        timeout_s=settings.timeout_s,
        transport=transport,
    )
