"""Provider usage extraction (token observability, §13 safety rule).

Responses optionally carry token counts. Shapes differ per API; this
helper tries the known layouts defensively and returns None when usage
is absent — the token-waste rule then stays dormant (documented), while
the acceptance-based breaker always works.

Never raises: observability must not break translation.
"""

from __future__ import annotations


def extract_usage(body: object) -> tuple[int, int] | None:
    """(input_tokens, output_tokens) from a response body, or None."""
    try:
        return _extract(body)
    except Exception:
        return None


def _extract(body: object) -> tuple[int, int] | None:
    if not isinstance(body, dict):
        return None
    # OpenAI-compatible: {"usage": {"prompt_tokens": N,
    #                                "completion_tokens": M}}.
    usage = body.get("usage")
    if isinstance(usage, dict):
        return _pair(usage.get("prompt_tokens"), usage.get("completion_tokens"))
    # Cohere v2 (best-effort; shape varies): try meta.tokens nests.
    meta = body.get("meta")
    if isinstance(meta, dict):
        tokens = meta.get("tokens")
        if isinstance(tokens, dict):
            return _pair(tokens.get("input_tokens"), tokens.get("output_tokens"))
        direct = _pair(meta.get("input_tokens"), meta.get("output_tokens"))
        if direct is not None:
            return direct
    return None


def _pair(first: object, second: object) -> tuple[int, int] | None:
    if isinstance(first, bool) or isinstance(second, bool):
        return None
    if isinstance(first, int) and isinstance(second, int):
        return (first, second)
    return None
