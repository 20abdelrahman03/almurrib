"""OpenAI-compatible chat-completions provider (stdlib-only HTTP).

One reusable implementation for any API that speaks the OpenAI
``POST {base_url}/chat/completions`` shape: OpenAI, OpenRouter, Kimi,
Gemini's OpenAI-compatible endpoint, local llama.cpp server, etc. Selection
is purely configuration (base_url + model + key) — the Core never knows
which one is in use.

* API key travels only in the Authorization header; never logged.
* Bounded exponential backoff on timeouts / connection errors / HTTP 429 / 5xx.
* Responses must be the strict JSON object our prompt demands; anything
  else raises InvalidResponseError without touching stored translations.
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
from almurrib.providers.prompts import build_messages
from almurrib.providers.usage import extract_usage


class _FormatRefusedError(ProviderError):
    """The server refused `response_format` (retry once without it)."""

    stage = "translate.api"


def _extract_error_message(raw: str) -> str | None:
    """Pull a human message out of an OpenAI-style error body.

    Expected shape: {"error": {"message": "...", "code": ...}}. Returns the
    message string, or None if the body isn't that shape. Never includes
    anything but the provider's own message — no headers, no keys.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    if isinstance(data, dict) and isinstance(data.get("message"), str):
        return data["message"]
    return None


class OpenAICompatibleProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self.last_fallback_calls: int = 0  # individual retries after bad batch
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

    def _payload(
        self, requests: list[TranslationRequest], *, structured: bool
    ) -> dict:
        payload: dict = {
            "model": self._config.model,
            "messages": build_messages(requests),
            "temperature": 0.2,
        }
        if structured:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def translate_batch(self, requests: list[TranslationRequest]) -> list[TranslationResult]:
        self.last_fallback_calls = 0
        structured = self._config.supports_json_object is not False
        try:
            body = self._post_json(self._payload(requests, structured=structured))
        except _FormatRefusedError:
            # The server (often a router fronting a model without JSON mode)
            # rejects response_format: retry once as plain structured text.
            # The prompt still demands strict JSON, so parsing is unchanged.
            structured = False
            body = self._post_json(self._payload(requests, structured=False))

        from almurrib.providers.batch_json import batch_or_fallback

        results, fallback_calls = batch_or_fallback(
            lambda: body,
            lambda req: self._post_json(self._payload([req], structured=structured)),
            self._parse_response,
            requests,
        )
        self.last_fallback_calls = fallback_calls
        return results


    # -- HTTP with bounded retry -------------------------------------------

    def _post_json(self, payload: dict) -> dict:
        url = self._config.base_url.rstrip("/") + "/chat/completions"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._config.api_key}",
        }

        attempts = self._config.max_retries + 1
        delay = 1.0
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            request = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=self._config.timeout_seconds) as resp:
                    self.last_http_status = getattr(resp, "status", None)
                    body = json.loads(resp.read().decode("utf-8"))
                    self.last_usage = extract_usage(body)
                    return body
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                provider_message = _extract_error_message(raw)
                detail = provider_message or raw[:300]
                if exc.code in (401, 403):
                    raise AuthenticationError(
                        f"invalid or missing API key (HTTP {exc.code})"
                        + (f": {detail}" if detail else ""),
                        hint="check the API key for the configured provider.",
                        http_status=exc.code,
                        provider_message=provider_message,
                    ) from exc
                if exc.code == 404:
                    raise ProviderError(
                        f"model or endpoint not found (HTTP 404)"
                        + (f": {detail}" if detail else ""),
                        hint="check ALMURRIB_MODEL and ALMURRIB_BASE_URL.",
                        http_status=exc.code,
                        provider_message=provider_message,
                    ) from exc
                if exc.code == 429:
                    last_error = RateLimitError(
                        f"rate limit exceeded (HTTP 429)"
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
                else:
                    if exc.code == 400 and (
                        "response_format" in (provider_message or "")
                        or "response_format" in raw
                    ):
                        raise _FormatRefusedError(
                            f"server refused response_format (HTTP 400)"
                            + (f": {detail}" if detail else ""),
                            hint="retrying once without structured output.",
                            http_status=exc.code,
                            provider_message=provider_message,
                        ) from exc
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
                delay *= 2.0  # bounded exponential backoff

        raise last_error or ProviderError("translation request failed")

    # -- response parsing ---------------------------------------------------

    def _parse_response(
        self, body: dict, requests: list[TranslationRequest]
    ) -> list[TranslationResult]:
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise InvalidResponseError(
                "response missing choices[0].message.content"
            ) from exc
        if not isinstance(content, str):
            raise InvalidResponseError(
                "response content was not text"
                f" (got {type(content).__name__}; tool-call/empty replies"
                " cannot be translated)"
            )

        from almurrib.providers.batch_json import parse_id_mapping

        return parse_id_mapping(
            content,
            requests,
            provider=self._config.provider,
            model=self._config.model,
        )
