"""Shared strict-JSON batch parsing for chat-style providers.

Both the generic OpenAI-compatible transport and native adapters (Cohere)
ask the model for the same contract: a JSON object mapping each requested
entry id to its translation. Parsing it once, here, keeps behavior and
error messages identical across providers.
"""

from __future__ import annotations

import json

from almurrib.core.errors import InvalidResponseError
from almurrib.core.provider import TranslationRequest, TranslationResult


def batch_or_fallback(post_all, post_one, parse, requests):
    """One policy for every chat provider: try the whole batch; on a
    malformed batch response, degrade to individual requests so one bad
    batch never loses entries that translate fine alone.

    ``post_all()`` sends the batch, ``post_one(req)`` a single request,
    ``parse(reply, reqs)`` interprets replies. Returns
    ``(results, fallback_calls)``. A single request that fails still raises.
    """
    try:
        return parse(post_all(), requests), 0
    except InvalidResponseError:
        if len(requests) <= 1:
            raise
        results: list[TranslationResult] = []
        fallback_calls = 0
        for req in requests:
            reply = post_one(req)
            fallback_calls += 1
            results.extend(parse(reply, [req]))
        return results, fallback_calls


def parse_id_mapping(
    content: str,
    requests: list[TranslationRequest],
    *,
    provider: str,
    model: str,
) -> list[TranslationResult]:
    """Parse a model text reply into per-entry translation results."""
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
                provider=provider,
                model=model,
            )
        )
    if missing and not results:
        raise InvalidResponseError(
            f"model output did not contain any requested ids (missing: {missing[:3]}...)"
        )
    return results
