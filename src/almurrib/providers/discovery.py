"""Model discovery: list available models without typing ids by hand.

Strategies are keyed by the provider definition's ``discovery`` field:
``openai`` parses ``{"data": [...]}`` (incl. OpenRouter extras like
``supported_parameters``/``pricing``); ``cohere`` parses ``{"models": [...]}``
with ``endpoints``/``context_length``/``features``. Secrets travel only in
the Authorization header and never appear in errors or logs.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field


# Where a model entry came from. Live provider data is authoritative for
# "can this key call it"; catalogs describe "what exists".
SOURCE_LIVE = "live"
SOURCE_MODELS_DEV = "models.dev"
SOURCE_LITELLM = "litellm"
SOURCE_STATIC = "static"
SOURCE_LOCAL = "local"

SOURCE_BADGES = {
    SOURCE_LIVE: "Live provider API",
    SOURCE_MODELS_DEV: "Models.dev",
    SOURCE_LITELLM: "LiteLLM catalog",
    SOURCE_STATIC: "Static fallback",
    SOURCE_LOCAL: "Local models",
}


@dataclass(frozen=True)
class ModelInfo:
    """One discoverable model; unknown metadata stays None (never guessed)."""

    id: str
    display_name: str | None = None
    provider: str | None = None  # our registry provider id
    context_length: int | None = None
    owner: str | None = None
    input_modalities: tuple[str, ...] | None = None
    output_modalities: tuple[str, ...] | None = None
    reasoning: bool | None = None
    tools: bool | None = None  # function/tool calling
    json_support: bool | None = None  # None = unknown / model-dependent
    free: bool | None = None  # None = unknown
    pricing: dict[str, float] = field(default_factory=dict)  # catalog units
    status: str | None = None  # e.g. "deprecated"; None = unknown
    source: str = SOURCE_LIVE
    retrieved_at: str = ""  # UTC ISO timestamp of when this was fetched
    extra: dict[str, str] = field(default_factory=dict)

    def short_label(self) -> str:
        parts = [self.id]
        tags: list[str] = []
        if self.free:
            tags.append("free")
        if self.json_support:
            tags.append("JSON")
        if self.context_length:
            if self.context_length >= 1000:
                tags.append(f"{self.context_length // 1000}k ctx")
            else:
                tags.append(f"{self.context_length} ctx")
        if tags:
            parts.append("(" + ", ".join(tags) + ")")
        return " ".join(parts)

    def details_line(self) -> str:
        """One-line metadata summary for the GUI (Unknown, never invented)."""
        def show(value, yes="yes", no="no"):
            return "Unknown" if value is None else (yes if value else no)

        parts = [
            f"context: {_fmt_ctx(self.context_length)}",
            f"JSON: {show(self.json_support)}",
            f"reasoning: {show(self.reasoning)}",
            f"tools: {show(self.tools)}",
            f"source: {SOURCE_BADGES.get(self.source, self.source or 'Unknown')}",
        ]
        if self.status:
            parts.append(f"status: {self.status}")
        return " • ".join(parts)


def _fmt_ctx(context_length: int | None) -> str:
    if context_length is None:
        return "Unknown"
    if context_length >= 1000:
        return f"{context_length // 1000}K"
    return str(context_length)


def utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_openai_models(body: dict) -> list[ModelInfo]:
    data = body.get("data")
    if not isinstance(data, list):
        from almurrib.core.errors import InvalidResponseError

        raise InvalidResponseError("model list response had no 'data' array")
    models: list[ModelInfo] = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        params = item.get("supported_parameters")
        json_support = (
            isinstance(params, list) and "response_format" in params
        ) or None
        if json_support is False:
            json_support = None
        free: bool | None = None
        pricing = item.get("pricing")
        if isinstance(pricing, dict):
            try:
                free = float(pricing.get("prompt", 1) or 1) == 0 and float(
                    pricing.get("completion", 1) or 1
                ) == 0
            except (TypeError, ValueError):
                free = None
        context = item.get("context_length") or item.get("context_window")
        models.append(
            ModelInfo(
                id=item["id"],
                display_name=item.get("name") if isinstance(item.get("name"), str) else None,
                context_length=context if isinstance(context, int) else None,
                owner=item.get("owned_by") if isinstance(item.get("owned_by"), str) else None,
                json_support=json_support,
                free=free,
            )
        )
    return models


def _parse_cohere_models(body: dict) -> list[ModelInfo]:
    items = body.get("models")
    if not isinstance(items, list):
        from almurrib.core.errors import InvalidResponseError

        raise InvalidResponseError("model list response had no 'models' array")
    models: list[ModelInfo] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        features = item.get("features")
        json_support: bool | None = None
        if isinstance(features, list) and "json_mode" in features:
            json_support = True
        context = item.get("context_length")
        models.append(
            ModelInfo(
                id=item["name"],
                context_length=context if isinstance(context, int) else None,
                json_support=json_support,
                extra={
                    "endpoints": ",".join(
                        e for e in (item.get("endpoints") or []) if isinstance(e, str)
                    )
                },
            )
        )
    return models


def fetch_models(
    *,
    base_url: str,
    api_key: str,
    models_path: str = "/models",
    discovery: str = "openai",
    timeout_seconds: float = 30.0,
) -> list[ModelInfo]:
    """GET the provider's model catalog. Raises stage-tagged ProviderErrors."""
    from almurrib.core.errors import (
        AuthenticationError,
        InvalidResponseError,
        ProviderError,
        ProviderTimeoutError,
        RateLimitError,
    )
    from almurrib.providers.openai_compat import _extract_error_message

    url = base_url.rstrip("/") + models_path
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as resp:
            try:
                body = json.loads(resp.read().decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise InvalidResponseError(
                    f"model list response was not valid JSON: {exc}"
                ) from exc
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        message = _extract_error_message(raw) or None
        detail = message or raw[:300]
        if exc.code in (401, 403):
            raise AuthenticationError(
                f"invalid or missing API key (HTTP {exc.code})"
                + (f": {detail}" if detail else ""),
                hint="check the API key for the configured provider.",
                http_status=exc.code,
                provider_message=message,
            ) from exc
        if exc.code == 404:
            raise ProviderError(
                "model listing not found (HTTP 404)"
                + (f": {detail}" if detail else ""),
                hint="this provider may not expose a models endpoint; "
                "enter the model id manually.",
                http_status=exc.code,
                provider_message=message,
            ) from exc
        if exc.code == 429:
            raise RateLimitError(
                f"rate limit exceeded (HTTP 429)"
                + (f": {detail}" if detail else ""),
                http_status=exc.code,
                provider_message=message,
            ) from exc
        raise ProviderError(
            f"model listing failed (HTTP {exc.code})"
            + (f": {detail}" if detail else ""),
            http_status=exc.code,
            provider_message=message,
        ) from exc
    except TimeoutError as exc:
        raise ProviderTimeoutError(f"model listing timed out: {exc}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError):
            raise ProviderTimeoutError(f"model listing timed out: {reason}") from exc
        raise ProviderError(f"model listing network error: {reason}") from exc

    if not isinstance(body, dict):
        raise InvalidResponseError("model list response JSON was not an object")
    parsed = (
        _parse_cohere_models(body) if discovery == "cohere"
        else _parse_openai_models(body)
    )
    stamped_at = utcnow_iso()
    import dataclasses

    return [
        dataclasses.replace(m, source=SOURCE_LIVE, retrieved_at=stamped_at)
        for m in parsed
    ]
