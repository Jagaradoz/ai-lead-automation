"""
providers.py
Model provider adapters for structured fact extraction.

Two adapter families cover every supported upstream:
- OpenAICompatibleProvider: any server speaking POST /chat/completions
  (OpenAI, OpenRouter, Groq, DeepSeek, Gemini's OpenAI endpoint, Ollama, LM Studio, vLLM, ...).
- AnthropicProvider: Claude via the official Anthropic SDK with structured outputs.

Both return a dict that has been validated against the caller's JSON schema,
or raise ProviderError with a message that is safe to show in the UI.
"""

import copy
import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from jsonschema import ValidationError, validate

# Keywords that strict structured-output modes reject; validated client-side instead.
_UNSUPPORTED_SCHEMA_KEYS = {"$schema", "title", "minimum", "maximum", "multipleOf", "format"}
_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
_MAX_ERROR_BODY = 300

# Claude models that accept server-side refusal fallbacks (fallbacks="default").
_ANTHROPIC_FALLBACK_MODELS = {"claude-opus-5", "claude-fable-5-1"}
_ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_ANTHROPIC_MAX_TOKENS = 16000


class ProviderError(Exception):
    """A model call failed. The message is safe to display (never contains secrets)."""


@dataclass(frozen=True)
class ExtractionRequest:
    system: str
    user: str
    schema: Dict[str, Any]
    name: str = "lead_analysis"


def to_strict_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a copy of `schema` accepted by strict structured-output modes:
    unsupported keywords removed, every object closed and all properties required.
    """

    def convert(node: Any) -> Any:
        if isinstance(node, list):
            return [convert(item) for item in node]
        if not isinstance(node, dict):
            return node
        out = {}
        for key, value in node.items():
            if key in _UNSUPPORTED_SCHEMA_KEYS:
                continue
            if key == "properties" and isinstance(value, dict):
                # Property names are data, not keywords: keep them all.
                out[key] = {name: convert(sub) for name, sub in value.items()}
            else:
                out[key] = convert(value)
        if out.get("type") == "object" and "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out["properties"].keys())
        return out

    return convert(copy.deepcopy(schema))


def _parse_json(text: str) -> Any:
    cleaned = (text or "").strip()
    match = _FENCE_RE.match(cleaned)
    if match:
        cleaned = match.group(1)
    return json.loads(cleaned)


def _check(data: Any, schema: Dict[str, Any]) -> Optional[str]:
    """Returns a validation error message, or None when `data` conforms."""
    try:
        validate(instance=data, schema=schema)
        return None
    except ValidationError as err:
        path = "/".join(str(p) for p in err.absolute_path) or "(root)"
        return f"{path}: {err.message}"


def _blocked_address(ip) -> bool:
    return ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved


def guard_destination(base_url: Optional[str]) -> None:
    """
    Refuses cloud-metadata, link-local, multicast and unspecified addresses so a
    configured base URL can't be used to probe them. Loopback and private
    addresses stay allowed for local model servers (Ollama, LM Studio, vLLM).
    """
    if not base_url:
        return
    host = urlparse(base_url).hostname or ""
    try:
        candidates = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            candidates = [ipaddress.ip_address(info[4][0].split("%")[0]) for info in socket.getaddrinfo(host, None)]
        except (OSError, UnicodeError, ValueError):
            return  # unresolvable: the request itself fails with a clear error
    if any(_blocked_address(ip) for ip in candidates):
        raise ProviderError(f"Requests to {host} are not allowed (link-local, metadata or reserved address).")


def _redact(text: str, secret: Optional[str]) -> str:
    return text.replace(secret, "[redacted]") if secret else text


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: Optional[str],
        model: str,
        timeout_s: float,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or None
        self._model = model
        self._timeout = timeout_s
        self._transport = transport

    def _client(self) -> httpx.Client:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return httpx.Client(
            base_url=self._base_url, headers=headers, timeout=self._timeout, transport=self._transport
        )

    def _error_from_response(self, resp: httpx.Response) -> ProviderError:
        if resp.status_code in (401, 403):
            return ProviderError(f"The provider rejected the API key ({resp.status_code}). Check the key in Settings.")
        if resp.status_code == 404:
            return ProviderError(f"Not found (404). Check the base URL and that model '{self._model}' exists.")
        if resp.status_code == 429:
            return ProviderError("The provider is rate limiting requests (429). Try again shortly.")
        body = _redact(resp.text[:_MAX_ERROR_BODY], self._api_key)
        return ProviderError(f"The provider returned {resp.status_code}: {body}")

    def _post_chat(self, client: httpx.Client, messages: List[Dict[str, str]], response_format: Dict[str, Any]) -> httpx.Response:
        payload = {
            "model": self._model,
            "messages": messages,
            "response_format": response_format,
            "temperature": 0,
        }
        try:
            return client.post("/chat/completions", json=payload)
        except httpx.TimeoutException:
            raise ProviderError(f"The model timed out after {self._timeout:g}s.")
        except httpx.HTTPError as err:
            raise ProviderError(f"Could not reach {self._base_url}: {type(err).__name__}.")

    @staticmethod
    def _content(resp: httpx.Response) -> str:
        try:
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("The provider returned an unexpected response shape.")

    def extract(self, request: ExtractionRequest) -> Dict[str, Any]:
        guard_destination(self._base_url)
        strict = to_strict_schema(request.schema)
        messages = [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.user},
        ]
        schema_format = {
            "type": "json_schema",
            "json_schema": {"name": request.name, "strict": True, "schema": strict},
        }

        with self._client() as client:
            response_format = schema_format
            resp = self._post_chat(client, messages, response_format)
            if resp.status_code in (400, 422):
                # Server lacks json_schema support: fall back to JSON mode with the schema in the prompt.
                response_format = {"type": "json_object"}
                messages = [
                    {
                        "role": "system",
                        "content": f"{request.system}\n\nReply with a single JSON object that conforms to this JSON schema:\n{json.dumps(strict)}",
                    },
                    {"role": "user", "content": request.user},
                ]
                resp = self._post_chat(client, messages, response_format)
            if resp.status_code >= 400:
                raise self._error_from_response(resp)

            content = self._content(resp)
            data, problem = self._parse_and_check(content, request.schema)
            if problem is None:
                return data

            repair = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": f"Your JSON failed validation: {problem}. Reply with the corrected JSON object only."},
            ]
            resp = self._post_chat(client, repair, response_format)
            if resp.status_code >= 400:
                raise self._error_from_response(resp)
            data, problem = self._parse_and_check(self._content(resp), request.schema)
            if problem is not None:
                raise ProviderError(f"The model returned invalid output twice ({problem}).")
            return data

    @staticmethod
    def _parse_and_check(content: str, schema: Dict[str, Any]):
        try:
            data = _parse_json(content)
        except (ValueError, TypeError):
            return None, "output is not valid JSON"
        return data, _check(data, schema)

    def list_models(self) -> List[str]:
        guard_destination(self._base_url)
        with self._client() as client:
            try:
                resp = client.get("/models")
            except httpx.TimeoutException:
                raise ProviderError(f"The provider timed out after {self._timeout:g}s.")
            except httpx.HTTPError as err:
                raise ProviderError(f"Could not reach {self._base_url}: {type(err).__name__}.")
            if resp.status_code >= 400:
                raise self._error_from_response(resp)
            try:
                return sorted(item["id"] for item in resp.json().get("data", []))
            except (ValueError, KeyError, TypeError):
                raise ProviderError("The provider returned an unexpected model list.")


class AnthropicProvider:
    def __init__(
        self,
        *,
        api_key: Optional[str],
        model: str,
        timeout_s: float,
        base_url: Optional[str] = None,
        client: Any = None,
    ):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        if client is None:
            import anthropic

            client = anthropic.Anthropic(
                api_key=api_key, base_url=base_url or None, timeout=timeout_s, max_retries=1
            )
        self._client = client
        self._timeout = timeout_s

    def _call(self, fn, **kwargs):
        import anthropic

        try:
            return fn(**kwargs)
        except anthropic.AuthenticationError:
            raise ProviderError("Anthropic rejected the API key (401). Check the key in Settings.")
        except anthropic.PermissionDeniedError:
            raise ProviderError("The API key lacks permission for this model (403).")
        except anthropic.NotFoundError:
            raise ProviderError(f"Model '{self._model}' was not found (404).")
        except anthropic.RateLimitError:
            raise ProviderError("Anthropic is rate limiting requests (429). Try again shortly.")
        except anthropic.APIStatusError as err:
            raise ProviderError(f"Anthropic returned {err.status_code}: {_redact(str(err.message), self._api_key)[:_MAX_ERROR_BODY]}")
        except anthropic.APITimeoutError:
            raise ProviderError(f"The model timed out after {self._timeout:g}s.")
        except anthropic.APIConnectionError:
            raise ProviderError("Could not reach the Anthropic API.")

    def extract(self, request: ExtractionRequest) -> Dict[str, Any]:
        guard_destination(self._base_url)
        kwargs = {
            "model": self._model,
            "max_tokens": _ANTHROPIC_MAX_TOKENS,
            "system": request.system,
            "messages": [{"role": "user", "content": request.user}],
            "output_config": {"format": {"type": "json_schema", "schema": to_strict_schema(request.schema)}},
        }
        if self._model in _ANTHROPIC_FALLBACK_MODELS:
            response = self._call(
                self._client.beta.messages.create,
                betas=[_ANTHROPIC_FALLBACK_BETA],
                fallbacks="default",
                **kwargs,
            )
        else:
            response = self._call(self._client.messages.create, **kwargs)

        if response.stop_reason == "refusal":
            raise ProviderError("The model declined to analyze this lead.")
        if response.stop_reason == "max_tokens":
            raise ProviderError("The model ran out of output tokens before finishing.")

        text = next((block.text for block in response.content if block.type == "text"), "")
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            raise ProviderError("The model returned invalid output (not JSON).")
        problem = _check(data, request.schema)
        if problem is not None:
            raise ProviderError(f"The model returned invalid output ({problem}).")
        return data

    def list_models(self) -> List[str]:
        page = self._call(self._client.models.list)
        return sorted(model.id for model in page)
