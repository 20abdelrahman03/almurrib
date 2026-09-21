"""Translation prompt construction.

The prompt is the contract between us and any chat-style API. It instructs
the model to translate ONLY the text, preserve placeholders/variables/
escapes/formatting verbatim, respect speaker/context, and return strict
JSON so responses are machine-checkable. Deliberately provider-neutral.
"""

from __future__ import annotations

from almurrib.core.provider import TranslationRequest

_SYSTEM = (
    "You are a professional video-game localization engine translating from "
    "@@SOURCE_LANG@@ to @@TARGET_LANG@@.\n"
    "Rules:\n"
    "1. Translate ONLY the provided game text. No explanations, no notes.\n"
    "2. Preserve ALL placeholders, variables, escape sequences and formatting "
    "tokens EXACTLY as-is. This includes tokens like {name}, {0}, %s, %d, "
    "<color=red>, </color>, [variable], and literal \\n sequences. Never "
    "translate, rename, reorder-remove, or alter them.\n"
    "3. Never translate identifiers, code, file names or tags.\n"
    "4. Respect the speaker and context when supplied (tone, gender, register).\n"
    "5. When glossary translations are supplied, use them for those terms.\n"
    "6. Output STRICT JSON only: an object mapping each id to its translation. "
    "No markdown, no code fences, no extra keys."
)

_BATCH_INSTRUCTION = (
    "Translate each of the following items. Each item has an id, the source "
    "text, and optional speaker/context. Return a JSON object like "
    '{"<id>": "<translation>", ...} covering every id exactly once.'
)


def build_messages(requests: list[TranslationRequest]) -> list[dict[str, str]]:
    """Build chat messages for a batch of translation requests."""
    if not requests:
        raise ValueError("requests must not be empty")
    source_lang = requests[0].source_lang
    target_lang = requests[0].target_lang

    lines = [_BATCH_INSTRUCTION, ""]
    for req in requests:
        parts = [f'id: {req.entry_id}', f'text: {req.source_text}']
        if req.speaker:
            who = req.speaker
            traits = ", ".join(t for t in (req.speaker_gender, req.speaker_style)
                               if t)
            if traits:
                who += f" ({traits})"
            parts.append(f"speaker: {who}")
        if req.context:
            parts.append(f"context: {req.context}")
        if req.placeholders:
            parts.append("placeholders (preserve exactly): " + ", ".join(req.placeholders))
        if req.glossary_terms:
            pairs = "; ".join(f"{src} -> {tgt}" for src, tgt in req.glossary_terms)
            parts.append("glossary (use these translations): " + pairs)
        lines.append(" | ".join(parts))

    system = _SYSTEM.replace("@@SOURCE_LANG@@", source_lang).replace(
        "@@TARGET_LANG@@", target_lang
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(lines)},
    ]
