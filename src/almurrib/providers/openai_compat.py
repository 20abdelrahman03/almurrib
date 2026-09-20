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


class OpenAICompatibleProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self._config = config

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_batch=True,
            supports_context=True,
            max_batch_size=self._config.batch_size,
        )

    # -- public API -------------------------------------------------------

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return self.translate_batch([request])[0]

    def translate_batch(self, requests: list[TranslationRequest]) -> list[TranslationResult]:
        payload = {
            "model": self._config.model,
            "messages": build_messages(requests),
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        body = self._post_json(payload)
        return self._parse_response(body, requests)


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
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
                if exc.code in (401, 403):
                    raise AuthenticationError(
                        f"provider rejected credentials (HTTP {exc.code})",
                        hint="check ALMURRIB_API_KEY for the configured provider.",
                    ) from exc
                if exc.code == 429:
                    last_error = RateLimitError(f"rate limited (HTTP 429): {detail}")
                elif 500 <= exc.code < 600:
                    last_error = ProviderError(f"server error (HTTP {exc.code}): {detail}")
                else:
                    raise ProviderError(f"HTTP {exc.code}: {detail}") from exc
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

        content = content.strip()
        if content.startswith("```"):  # tolerate code fences despite instructions
            content = content.strip("`")
            content = content[content.find("\n") + 1 :] if "\n" in content else content
        try:
            mapping = json.loads(content)
        except json.JSONDecodeError as exc:
            raise InvalidResponseError(
                f"model output was not a JSON object: {content[:120]!r}"
            ) from exc
        if not isinstance(mapping, dict):
            raise InvalidResponseError("model output JSON was not an object")

        results: list[TranslationResult] = []
        missing: list[str] = []
        for req in requests:
            text = mapping.get(req.entry_id)
            if not isinstance(text, str) or not text.strip():
                missing.append(req.entry_id)
                continue
            results.append(
                TranslationResult(
                    entry_id=req.entry_id,
                    translated_text=text,
                    provider=self._config.provider,
                    model=self._config.model,
                )
            )
        if missing and not results:
            raise InvalidResponseError(
                f"model output did not contain any requested ids (missing: {missing[:3]}...)"
            )
        return results
