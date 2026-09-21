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
