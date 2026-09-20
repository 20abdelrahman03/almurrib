"""Translation stage: real execution of the Translate pipeline stage.

Flow per the design:

    entries
      -> skip already-translated (unless forced)
      -> translation memory reuse (fingerprint match, context-safe)
      -> cache lookup (provider+model+lang keyed)
      -> provider.translate_batch(remaining)
      -> placeholder validation
      -> persist + cache save

The Core stays provider-agnostic: it only knows the TranslationProvider
protocol. Cache keys include provider identity (name:model) and both
languages, so a translation from one model/config is never reused for
another.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from almurrib.core.cache import DEFAULT_PROVIDER, make_cache_key
from almurrib.core.model import EntryStatus, LocalizationEntry
from almurrib.core.placeholders import extract_placeholders, validate_translation
from almurrib.core.provider import TranslationProvider, TranslationRequest


@dataclass
class TranslationStats:
    total: int = 0
    already_translated: int = 0
    memory_hits: int = 0
    cache_hits: int = 0
    api_calls: int = 0
    api_translated: int = 0
    placeholder_failures: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class _MemoryView:
    """Translation memory: fingerprint -> previously stored translation."""

    def __init__(self, candidates: dict[str, str]) -> None:
        self._candidates = candidates

    def lookup(self, entry: LocalizationEntry) -> str | None:
        return self._candidates.get(entry.fingerprint)


class RealTranslateStage:
    """Pipeline TranslateStage backed by a provider, cache and TM."""

    name = "translate"

    def __init__(
        self,
        provider: TranslationProvider,
        *,
        cache=None,  # TranslationCache or SQLiteCache (duck-typed)
        memory: dict[str, str] | None = None,  # fingerprint -> translation
        force: bool = False,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.memory = _MemoryView(memory or {})
        self.force = force

    # -- pipeline protocol ------------------------------------------------

    def translate(self, result, context):
        stats = self.run(
            result.entries,
            source_lang=context.source_lang,
            target_lang=context.target_lang,
        )
        result.metadata = getattr(result, "metadata", None) or {}
        result.metadata["translation_stats"] = stats.__dict__
        return result

    # -- core logic ---------------------------------------------------------

    def run(
        self,
        entries: list[LocalizationEntry],
        *,
        source_lang: str = "en",
        target_lang: str = "ar",
    ) -> TranslationStats:
        stats = TranslationStats(total=len(entries))
        pending: list[LocalizationEntry] = []

        for entry in entries:
            if entry.translated_text and not self.force:
                stats.already_translated += 1
                continue

            # 1. translation memory (same fingerprint seen before)
            tm_hit = self.memory.lookup(entry)
            if tm_hit is not None:
                entry.translated_text = tm_hit
                entry.status = EntryStatus.TRANSLATED
                stats.memory_hits += 1
                continue

            # 2. cache (provider+model+lang specific)
            if self.cache is not None:
                record = self.cache.lookup(entry)
                if record is not None and record.translated_text:
                    entry.translated_text = record.translated_text
                    entry.status = EntryStatus.TRANSLATED
                    stats.cache_hits += 1
                    continue

            pending.append(entry)

        # 3. provider batch translation for what is left
        if pending:
            self._translate_pending(pending, source_lang, target_lang, stats)

        return stats

    def _translate_pending(
        self,
        entries: list[LocalizationEntry],
        source_lang: str,
        target_lang: str,
        stats: TranslationStats,
    ) -> None:
        batch_size = max(1, self.provider.config.batch_size)
        for start in range(0, len(entries), batch_size):
            chunk = entries[start : start + batch_size]
            requests = [
                TranslationRequest(
                    entry_id=e.id,
                    source_text=e.source_text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    speaker=e.speaker,
                    context=e.context,
                    placeholders=extract_placeholders(e.source_text),
                )
                for e in chunk
            ]
            by_id = {e.id: e for e in chunk}
            try:
                results = self.provider.translate_batch(requests)
                stats.api_calls += 1
            except Exception as exc:  # provider errors already stage-tagged
                stats.failed += len(chunk)
                stats.errors.append(str(exc))
                continue

            for res in results:
                entry = by_id.get(res.entry_id)
                if entry is None:
                    continue
                report = validate_translation(entry.source_text, res.translated_text)
                if not report.ok:
                    stats.placeholder_failures += 1
                    entry.qa_flags.append(
                        "placeholder_missing:" + ",".join(report.missing)
                    )
                entry.translated_text = res.translated_text
                entry.status = (
                    EntryStatus.TRANSLATED if report.ok else EntryStatus.FLAGGED
                )
                stats.api_translated += 1
                if self.cache is not None:
                    self.cache.remember(entry, res.translated_text)


def make_provider_key(label: str) -> str:
    """Helper for callers building caches manually."""
    return label or DEFAULT_PROVIDER


def cache_key_for(entry: LocalizationEntry, *, target_lang: str, provider_label: str) -> str:
    return make_cache_key(entry, target_lang=target_lang, provider=provider_label)
