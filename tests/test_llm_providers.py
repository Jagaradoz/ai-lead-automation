"""
test_llm_providers.py
Unit tests for the model provider adapters (OpenAI-compatible + Anthropic).
HTTP is mocked with httpx.MockTransport; the Anthropic SDK client is replaced by a fake.
"""

import json
from types import SimpleNamespace

import httpx
import pytest

from scripts.llm.providers import (
    AnthropicProvider,
    ExtractionRequest,
    OpenAICompatibleProvider,
    ProviderError,
    to_strict_schema,
)

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Tiny",
    "type": "object",
    "required": ["label", "confidence"],
    "properties": {
        "label": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "nested": {
            "type": "object",
            "properties": {"x": {"type": ["string", "null"]}},
        },
    },
    "additionalProperties": False,
}
REQUEST = ExtractionRequest(system="sys", user="usr", schema=SCHEMA)
VALID = {"label": "ok", "confidence": 0.9, "nested": {"x": None}}


def chat_response(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})


def make_openai(handler, **kwargs) -> OpenAICompatibleProvider:
    params = {
        "base_url": "https://llm.example.com/v1",
        "api_key": "sk-secret-123456",
        "model": "test-model",
        "timeout_s": 5,
    }
    params.update(kwargs)
    return OpenAICompatibleProvider(transport=httpx.MockTransport(handler), **params)


# --- Strict schema conversion -------------------------------------------------

def test_strict_schema_strips_unsupported_keywords_and_requires_all_properties():
    strict = to_strict_schema(SCHEMA)

    assert "$schema" not in strict and "title" not in strict
    assert "minimum" not in strict["properties"]["confidence"]
    assert "maximum" not in strict["properties"]["confidence"]
    assert strict["required"] == ["label", "confidence", "nested"]
    assert strict["properties"]["nested"]["additionalProperties"] is False
    assert strict["properties"]["nested"]["required"] == ["x"]
    # Original schema is not mutated
    assert "minimum" in SCHEMA["properties"]["confidence"]


# --- OpenAI-compatible provider ----------------------------------------------

def test_openai_sends_strict_json_schema_request():
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        return chat_response(json.dumps(VALID))

    result = make_openai(handler).extract(REQUEST)

    assert result == VALID
    req = seen[0]
    assert str(req.url) == "https://llm.example.com/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer sk-secret-123456"
    body = json.loads(req.content)
    assert body["model"] == "test-model"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert "minimum" not in json.dumps(body["response_format"])
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_openai_omits_auth_header_when_no_key():
    seen = []

    def handler(request):
        seen.append(request)
        return chat_response(json.dumps(VALID))

    make_openai(handler, api_key=None).extract(REQUEST)
    assert "authorization" not in seen[0].headers


def test_openai_downgrades_to_json_object_when_schema_mode_rejected():
    formats = []

    def handler(request):
        body = json.loads(request.content)
        formats.append(body["response_format"]["type"])
        if body["response_format"]["type"] == "json_schema":
            return httpx.Response(400, json={"error": {"message": "response_format json_schema not supported"}})
        assert "label" in body["messages"][0]["content"]  # schema embedded in system prompt
        return chat_response(json.dumps(VALID))

    assert make_openai(handler).extract(REQUEST) == VALID
    assert formats == ["json_schema", "json_object"]


def test_openai_repairs_invalid_output_once():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            return chat_response(json.dumps({"label": "ok", "confidence": 7}))
        assert "failed validation" in body["messages"][-1]["content"]
        return chat_response(json.dumps(VALID))

    assert make_openai(handler).extract(REQUEST) == VALID
    assert len(calls) == 2


def test_openai_raises_when_repair_also_invalid():
    def handler(request):
        return chat_response("not json at all")

    with pytest.raises(ProviderError, match="invalid"):
        make_openai(handler).extract(REQUEST)


def test_openai_parses_fenced_json():
    def handler(request):
        return chat_response("```json\n" + json.dumps(VALID) + "\n```")

    assert make_openai(handler).extract(REQUEST) == VALID


def test_openai_auth_error_is_readable_and_hides_key():
    def handler(request):
        return httpx.Response(401, json={"error": {"message": "Incorrect API key provided: sk-secret-123456"}})

    with pytest.raises(ProviderError) as exc:
        make_openai(handler).extract(REQUEST)
    assert "rejected" in str(exc.value).lower()
    assert "sk-secret-123456" not in str(exc.value)


def test_openai_timeout_is_reported():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderError, match="timed out"):
        make_openai(handler).extract(REQUEST)


def test_openai_connection_error_is_reported():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(ProviderError, match="reach"):
        make_openai(handler).extract(REQUEST)


def test_openai_list_models():
    def handler(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "b-model"}, {"id": "a-model"}]})

    assert make_openai(handler).list_models() == ["a-model", "b-model"]


# --- Anthropic provider -------------------------------------------------------

class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def fake_anthropic_client(text: str, stop_reason: str = "end_turn"):
    response = SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
    )
    return SimpleNamespace(
        messages=FakeMessages(response),
        beta=SimpleNamespace(messages=FakeMessages(response)),
    )


def test_anthropic_uses_structured_output_format():
    client = fake_anthropic_client(json.dumps(VALID))
    provider = AnthropicProvider(api_key="k", model="claude-haiku-4-5", timeout_s=5, client=client)

    assert provider.extract(REQUEST) == VALID
    call = client.messages.calls[0]
    assert call["model"] == "claude-haiku-4-5"
    assert call["system"] == "sys"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert "minimum" not in json.dumps(call["output_config"])
    assert client.beta.messages.calls == []


def test_anthropic_opus_enables_server_side_fallbacks():
    client = fake_anthropic_client(json.dumps(VALID))
    provider = AnthropicProvider(api_key="k", model="claude-opus-5", timeout_s=5, client=client)

    provider.extract(REQUEST)
    call = client.beta.messages.calls[0]
    assert call["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in call["betas"]


def test_anthropic_refusal_raises():
    client = fake_anthropic_client("", stop_reason="refusal")
    provider = AnthropicProvider(api_key="k", model="claude-haiku-4-5", timeout_s=5, client=client)

    with pytest.raises(ProviderError, match="declined"):
        provider.extract(REQUEST)


def test_anthropic_validates_output_client_side():
    client = fake_anthropic_client(json.dumps({"label": "x", "confidence": 5}))
    provider = AnthropicProvider(api_key="k", model="claude-haiku-4-5", timeout_s=5, client=client)

    with pytest.raises(ProviderError, match="invalid"):
        provider.extract(REQUEST)


def test_metadata_and_link_local_destinations_are_blocked():
    def handler(request):  # pragma: no cover - must never be reached
        raise AssertionError("request should have been blocked")

    for url in ("http://169.254.169.254/v1", "http://[fe80::1]/v1", "http://0.0.0.0:8000/v1"):
        with pytest.raises(ProviderError, match="not allowed"):
            make_openai(handler, base_url=url).extract(REQUEST)


def test_local_servers_are_allowed():
    def handler(request):
        return chat_response(json.dumps(VALID))

    assert make_openai(handler, base_url="http://127.0.0.1:11434/v1").extract(REQUEST) == VALID
