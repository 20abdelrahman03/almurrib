"""Cohere native provider (Chat API v2 primary, v1 fallback).

Cohere exposes no first-party OpenAI-compatible endpoint, so it gets the
one specialized adapter in the ecosystem. Verified against the official
docs (2026-09):

* ``POST {base_url}/v2/chat`` with ``{model, messages, response_format}``;
  reply text at ``message.content[].text`` (``type == "text"`` blocks).
* Version routing is automatic: a 400 demanding the other API version
  retries once on it (new models require v2, legacy models may need v1).
* Discovery still uses ``GET /v1/models`` (current per the API reference).

The reply text is parsed against the same strict batch-JSON contract every
provider honors (see ``providers/batch_json.py``). Command A Translate
(``command-a-translate-...``) is Cohere's translation-specialized family
incl. Arabic; selectable like any other model id — never hard-coded here.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from almurrib.core.errors import (
    AuthenticationError,
    InvalidResponseError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
)
from almurrib.core.provider import (
    ProviderCapabilities,
    ProviderConfig,
    TranslationRequest,
    TranslationResult,
)
from almurrib.providers.batch_json import parse_id_mapping
from almurrib.providers.openai_compat import _extract_error_message
from almurrib.providers.prompts import build_messages
from almurrib.providers.usage import extract_usage


class _VersionFallback(ProviderError):
    """The model needs the other Cohere API version (retry once there)."""

    stage = "translate.api"


class _FormatRefusedError(ProviderError):
    """The server refused response_format (retry once without it)."""

    stage = "translate.api"


def _to_v2_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Generic chat messages -> v2 ``messages`` (system first, then user)."""
    system = [m.get("content", "") for m in messages if m.get("role") == "system"]
    user = [m.get("content", "") for m in messages if m.get("role") != "system"]
    out: list[dict[str, str]] = []
    if system:
        out.append({"role": "system", "content": "\n".join(system)})
    out.append({"role": "user", "content": "\n".join(user)})
    return out


def _to_v1_payload(messages: list[dict[str, str]], model: str) -> dict:
    """Generic chat messages -> legacy v1 ``{preamble, message}`` shape."""
    preamble = "\n".join(
        m.get("content", "") for m in messages if m.get("role") == "system"
    )
    user = "\n".join(
        m.get("content", "") for m in messages if m.get("role") != "system"
    )
    payload = {"model": model, "message": user, "temperature": 0.2}
    if preamble:
        payload["preamble"] = preamble
    return payload


class CohereProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self.last_fallback_calls: int = 0
        self.last_http_status: int | None = None  # observability (never secrets)
        self.last_usage: tuple[int, int] | None = None  # (in, out) or None

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_batch=True,
            supports_context=True,
            max_batch_size=self._config.batch_size,
            supports_json_object=self._config.supports_json_object,
            supports_model_list=True,
            supports_chat=True,
        )

    # -- public API -------------------------------------------------------

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return self.translate_batch([request])[0]

    def translate_batch(self, requests: list[TranslationRequest]) -> list[TranslationResult]:
        self.last_fallback_calls = 0
        from almurrib.providers.batch_json import batch_or_fallback

        results, fallback_calls = batch_or_fallback(
            lambda: self._post_chat(build_messages(requests)),
            lambda req: self._post_chat(build_messages([req])),
            self._parse_text,
            requests,
        )
        self.last_fallback_calls = fallback_calls
        return results

    def _parse_text(
        self, text: str, requests: list[TranslationRequest]
    ) -> list[TranslationResult]:
        return parse_id_mapping(
            text, requests, provider=self._config.provider, model=self._config.model
        )

    # -- HTTP with bounded retry -------------------------------------------

    def _post_chat(self, messages: list[dict[str, str]]) -> str:
        structured = self._config.supports_json_object is not False
        try:
            return self._post_v2(messages, structured=structured)
        except _VersionFallback:
            # Legacy model bound to v1: same contract, older wire shape.
            return self._post_v1(messages)
        except _FormatRefusedError:
            return self._post_v2(messages, structured=False)

    def _request(
        self, path: str, payload: dict
    ) -> urllib.request.Request:
        return urllib.request.Request(
            self._config.base_url.rstrip("/") + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._config.api_key}",
            },
            method="POST",
        )

    def _post_v2(self, messages: list[dict[str, str]], *, structured: bool) -> str:
        payload: dict = {
            "model": self._config.model,
            "messages": _to_v2_messages(messages),
            "temperature": 0.2,
        }
        if structured:
            payload["response_format"] = {"type": "json_object"}
        body = self._send(self._request("/v2/chat", payload))
        return self._read_v2_text(body)

    def _post_v1(self, messages: list[dict[str, str]]) -> str:
        body = self._send(
            self._request("/v1/chat", _to_v1_payload(messages, self._config.model))
        )
        return self._read_v1_text(body)

    def _send(self, request: urllib.request.Request) -> dict:
        attempts = self._config.max_retries + 1
        delay = 1.0
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                with urllib.request.urlopen(request, timeout=self._config.timeout_seconds) as resp:
                    self.last_http_status = getattr(resp, "status", None)
                    body = json.loads(resp.read().decode("utf-8"))
                    self.last_usage = extract_usage(body)
                    return body
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                provider_message = _extract_error_message(raw) or _cohere_message(raw)
                detail = provider_message or raw[:300]
                if exc.code in (401, 403):
                    raise AuthenticationError(
                        f"invalid or missing API key (HTTP {exc.code})"
                        + (f": {detail}" if detail else ""),
                        hint="check the Cohere API key.",
                        http_status=exc.code,
                        provider_message=provider_message,
                    ) from exc
                if exc.code == 404:
                    raise ProviderError(
                        "model or endpoint not found (HTTP 404)"
                        + (f": {detail}" if detail else ""),
                        hint="check the Cohere model id (fetch models to list).",
                        http_status=exc.code,
                        provider_message=provider_message,
                    ) from exc
                if exc.code == 429:
                    last_error = RateLimitError(
                        f"rate limit exceeded (HTTP {exc.code})"
                        + (f": {detail}" if detail else ""),
                        http_status=exc.code,
                        provider_message=provider_message,
                    )
                elif 500 <= exc.code < 600:
                    last_error = ProviderError(
                        f"provider server error (HTTP {exc.code})"
                        + (f": {detail}" if detail else ""),
                        http_status=exc.code,
                        provider_message=provider_message,
                    )
                elif exc.code == 400 and _mentions(raw, provider_message, "/v1/chat"):
                    raise _VersionFallback(
                        "model requires Cohere API v1 (HTTP 400)"
                        + (f": {detail}" if detail else ""),
                        hint="retrying once on /v1/chat.",
                        http_status=exc.code,
                        provider_message=provider_message,
                    ) from exc
                elif exc.code == 400 and _mentions(
                    raw, provider_message, "response_format", "json_object", "/v2/chat"
                ):
                    raise _FormatRefusedError(
                        "server refused response_format (HTTP 400)"
                        + (f": {detail}" if detail else ""),
                        hint="retrying once without structured output.",
                        http_status=exc.code,
                        provider_message=provider_message,
                    ) from exc
                else:
                    # The observed v1-side refusal ("use '/v2/chat' instead")
                    # arrives here when posting to v1; v2 is already primary,
                    # so surface it plainly.
                    raise ProviderError(
                        f"HTTP {exc.code}" + (f": {detail}" if detail else ""),
                        http_status=exc.code,
                        provider_message=provider_message,
                    ) from exc
            except TimeoutError as exc:
                last_error = ProviderTimeoutError(f"request timed out: {exc}")
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", exc)
                if isinstance(reason, TimeoutError):
                    last_error = ProviderTimeoutError(f"request timed out: {reason}")
                else:
                    last_error = ProviderError(f"network error: {reason}")
            except json.JSONDecodeError as exc:
                raise InvalidResponseError(f"response was not valid JSON: {exc}") from exc

            if attempt < attempts:
                time.sleep(delay)
                delay *= 2.0

        raise last_error or ProviderError("translation request failed")

    @staticmethod
    def _read_v2_text(body: dict) -> str:
        """Assistant text from a v2/chat reply: message.content[].text."""
        message = body.get("message")
        if isinstance(message, dict):
            parts = []
            for block in message.get("content", []) or []:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "text"
                    and isinstance(block.get("text"), str)
                ):
                    parts.append(block["text"])
            if parts:
                return "".join(parts)
        raise InvalidResponseError("Cohere v2 response had no reply text")

    @staticmethod
    def _read_v1_text(body: dict) -> str:
        """Assistant text from a v1/chat reply (both known shapes)."""
        if isinstance(body.get("text"), str):
            return body["text"]
        generations = body.get("generations")
        if isinstance(generations, list) and generations:
            first = generations[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                return first["text"]
        raise InvalidResponseError("Cohere response had no reply text")


def _mentions(raw: str, provider_message: str | None, *needles: str) -> bool:
    haystack = f"{raw}\n{provider_message or ''}".lower()
    return any(needle.lower() in haystack for needle in needles)


def _cohere_message(raw: str) -> str | None:
    """Cohere errors are {"message": ...} (no nested "error" object)."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(data, dict) and isinstance(data.get("message"), str):
        return data["message"]
    return None
