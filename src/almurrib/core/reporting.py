"""User-facing translation failure reporting (shared by CLI and GUI).

One formatter, one vocabulary: stage, provider, model, HTTP status, provider
message, retry behavior and a recommended action. Never includes secrets —
callers pass only display strings, never keys or headers.
"""

from __future__ import annotations

import re

# Providers sometimes echo a (masked) key fragment back inside error text,
# e.g. "Incorrect API key provided: HlDv****TfgL". Exact-match redaction
# misses those, so credential-shaped patterns are masked structurally.
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9_\-\.~]+")
_ECHOED_KEY_RE = re.compile(r"(Incorrect API key provided:\s*)\S+")


def redact_secrets(text: str, secrets: list[str | None]) -> str:
    """Strip secrets from text bound for logs, dialogs or the clipboard."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    text = _BEARER_RE.sub("Bearer ***", text)
    text = _ECHOED_KEY_RE.sub(r"\1***", text)
    return text


def format_translation_summary(stats) -> str:
    """One-line success summary; already-translated entries count as done."""
    done = (
        stats.api_translated
        + stats.cache_hits
        + stats.memory_hits
        + stats.already_translated
    )
    parts = [
        f"{done}/{stats.total} translated",
        f"(already={stats.already_translated}",
        f"api={stats.api_translated}",
        f"cache={stats.cache_hits}",
        f"memory={stats.memory_hits}",
        f"failed={stats.failed}",
    ]
    if getattr(stats, "fallback_calls", 0):
        parts.append(f"fallback={stats.fallback_calls}")
    if stats.placeholder_failures:
        parts.append(f"flagged={stats.placeholder_failures}")
    return " ".join(parts) + ")"


def suggest_for(http_status: int | None, first_error: str | None = None) -> str | None:
    """Recommended action for a translation failure cause."""
    if http_status in (401, 403):
        return "Check the API key for the configured provider, then retry."
    if http_status == 404:
        return "Check the model id and Base URL (fetch the model list to pick a valid id)."
    if http_status == 429:
        return "Wait and retry, reduce batch size, or switch provider."
    text = (first_error or "").lower()
    if http_status is None and ("timed out" in text or "timeout" in text):
        return "Increase the timeout or reduce batch size, then retry."
    if "json" in text or "response" in text:
        return "Use a JSON-capable model or smaller batches, then retry."
    if "network" in text:
        return "Check the network connection and endpoint URL, then retry."
    return None


def provider_display_name(provider_id: str, fallback: str) -> str:
    """Human provider label from the registry, falling back to the identity."""
    try:
        from almurrib.providers.registry import get_definition

        definition = get_definition(provider_id)
        if definition is not None:
            return definition.display_name
    except Exception:
        pass
    return fallback


def format_translation_error(
    *,
    provider: str,
    base_url: str,
    model: str,
    stats,
    retries: int | None = None,
) -> str:
    """Build the user-facing translation-failure message (no secrets).

    ``stats`` is duck-typed (only ``failed``/``total``/``first_error``/
    ``first_http_status``/``first_provider_message`` are read).
    """
    lines = [
        f"Translation failed ({stats.failed}/{stats.total} failed)",
        f"Provider: {provider}",
        f"Base URL: {base_url}",
        f"Model: {model}",
    ]
    status = getattr(stats, "first_http_status", None)
    message = getattr(stats, "first_provider_message", None)
    if status is not None:
        lines.append(f"HTTP Status: {status}")
    if message:
        lines.append(f"Message: {message}")
    cause = getattr(stats, "first_error", None) or "unknown provider error"
    if not message or message not in cause:
        lines.append(f"Cause: {cause}")
    if retries is not None:
        lines.append(f"Retries: {retries} (bounded exponential backoff)")
    suggestion = suggest_for(status, cause)
    if suggestion:
        lines.append(f"Suggestion: {suggestion}")
    return "\n".join(lines)
