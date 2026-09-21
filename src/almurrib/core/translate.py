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
from almurrib.core.model import EntryStatus, LocalizationEntry, TranslationSource
from almurrib.core.placeholders import extract_placeholders, validate_translation
from almurrib.core.provider import TranslationProvider, TranslationRequest


@dataclass
class TranslationStats:
    total: int = 0
    already_translated: int = 0
    memory_hits: int = 0
    cache_hits: int = 0
    api_calls: int = 0
    fallback_calls: int = 0  # individual requests after a malformed batch
    api_translated: int = 0
    placeholder_failures: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    first_error: str | None = None  # the first provider failure cause
    first_http_status: int | None = None  # structured HTTP status, if known
    first_provider_message: str | None = None  # provider's own message, if any


@dataclass(frozen=True)
class TMRecord:
    """One translation-memory candidate with its provenance."""

    text: str
    source: str = TranslationSource.MACHINE.value
    provider: str | None = None  # provider identity ("name:model"), if known
    model: str | None = None


def tm_reusable(
    record: TMRecord, *, current_identity: str, allow_cross_model_machine: bool
) -> bool:
    """Decide whether a TM candidate may satisfy the current run.

    Human/imported work is universal. Machine output is only reused for the
    same provider:model that produced it — unless the caller explicitly opts
    into cross-model machine reuse. Legacy machine records with unknown
    provenance (provider None, e.g. pre-provenance databases) are
    grandfathered as reusable so existing work keeps flowing.
    """
    if record.source in (TranslationSource.HUMAN.value, TranslationSource.IMPORTED.value):
        return True
    if record.source == TranslationSource.MACHINE.value:
        if record.provider is None:
            return True  # legacy rows predate provenance tracking
        return allow_cross_model_machine or record.provider == current_identity
    return False


class _MemoryView:
    """Translation memory: fingerprint -> TMRecord (provenance-aware)."""

    def __init__(self, candidates: dict[str, TMRecord | str]) -> None:
        normalized: dict[str, TMRecord] = {}
        for key, value in candidates.items():
            normalized[key] = (
                value if isinstance(value, TMRecord)
                else TMRecord(text=value)  # legacy plain-text mapping
            )
        self._candidates = normalized

    def lookup(self, entry: LocalizationEntry) -> TMRecord | None:
        return self._candidates.get(entry.fingerprint)


class RealTranslateStage:
    """Pipeline TranslateStage backed by a provider, cache and TM."""

    name = "translate"

    def __init__(
        self,
        provider: TranslationProvider,
        *,
        cache=None,  # TranslationCache or SQLiteCache (duck-typed)
        memory: dict[str, TMRecord | str] | None = None,  # fingerprint -> record
        force: bool = False,
        reuse_machine_tm: bool = False,
    ) -> None:
        """Force semantics: ignore already-translated text, TM and cache
        reads; the provider is called again and provenance is overwritten.
        ``reuse_machine_tm`` permits cross-model reuse of machine TM
        (default False: same provider:model or human/imported only).
        """
        self.provider = provider
        self.cache = cache
        self.memory = _MemoryView(memory or {})
        self.force = force
        self.reuse_machine_tm = reuse_machine_tm

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
        progress=None,  # optional callable(done: int, total: int)
    ) -> TranslationStats:
        # Obsolete entries vanished from source: never translate, never count,
        # so progress and totals stay exact across repeated runs.
        entries = [e for e in entries if e.status is not EntryStatus.OBSOLETE]
        stats = TranslationStats(total=len(entries))
        pending: list[LocalizationEntry] = []
        done = 0

        def tick() -> None:
            if progress is not None:
                progress(done, stats.total)

        identity = self.provider.config.identity
        for entry in entries:
            if entry.translated_text and not self.force:
                stats.already_translated += 1
                done += 1
                tick()
                continue

            # 1. translation memory (provenance-gated, skipped under force)
            if not self.force:
                tm_hit = self.memory.lookup(entry)
                if tm_hit is not None and tm_reusable(
                    tm_hit,
                    current_identity=identity,
                    allow_cross_model_machine=self.reuse_machine_tm,
                ):
                    entry.translated_text = tm_hit.text
                    entry.translation_source = tm_hit.source
                    entry.translation_provider = (
                        tm_hit.provider.split(":")[0] if tm_hit.provider else None
                    )
                    entry.translation_model = tm_hit.model
                    entry.status = EntryStatus.TRANSLATED
                    stats.memory_hits += 1
                    done += 1
                    tick()
                    continue

            # 2. cache (provider+model+lang specific, skipped under force)
            if self.cache is not None and not self.force:
                record = self.cache.lookup(entry)
                if record is not None and record.translated_text:
                    entry.translated_text = record.translated_text
                    entry.status = EntryStatus.TRANSLATED
                    stats.cache_hits += 1
                    done += 1
                    tick()
                    continue

            pending.append(entry)

        # 3. provider batch translation for what is left
        if pending:
            self._translate_pending(
                pending, source_lang, target_lang, stats,
                progress=progress, done_offset=done,
            )

        return stats

    def _translate_pending(
        self,
        entries: list[LocalizationEntry],
        source_lang: str,
        target_lang: str,
        stats: TranslationStats,
        *,
        progress=None,
        done_offset: int = 0,
    ) -> None:
        batch_size = max(1, self.provider.config.batch_size)
        total = stats.total
        done = done_offset
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
                stats.fallback_calls += int(
                    getattr(self.provider, "last_fallback_calls", 0) or 0
                )
            except Exception as exc:  # provider errors already stage-tagged
                stats.failed += len(chunk)
                stats.errors.append(str(exc))
                # Surface the first real cause instead of silently counting.
                if stats.first_error is None:
                    from almurrib.core.errors import ProviderError

                    stats.first_error = str(exc)
                    if isinstance(exc, ProviderError):
                        stats.first_http_status = exc.http_status
                        stats.first_provider_message = exc.provider_message
                continue

            returned_ids = {res.entry_id for res in results}
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
                entry.translation_provider = self.provider.config.provider
                entry.translation_model = self.provider.config.model
                entry.translation_source = TranslationSource.MACHINE.value
                stats.api_translated += 1
                if report.ok and self.cache is not None:
                    # Broken translations are persisted as FLAGGED for review
                    # but must never poison the cache as good translations.
                    self.cache.remember(entry, res.translated_text)
                done += 1
                if progress is not None:
                    progress(done, total)

            # A partial batch must not silently drop entries: anything the
            # provider did not return stays untranslated AND is counted.
            for missing_id, missing_entry in by_id.items():
                if missing_id not in returned_ids and not missing_entry.translated_text:
                    stats.failed += 1
                    stats.errors.append(
                        f"provider did not return a translation for entry {missing_id}"
                    )
                    done += 1
                    if progress is not None:
                        progress(done, total)


def make_provider_key(label: str) -> str:
    """Helper for callers building caches manually."""
    return label or DEFAULT_PROVIDER


def cache_key_for(entry: LocalizationEntry, *, target_lang: str, provider_label: str) -> str:
    return make_cache_key(entry, target_lang=target_lang, provider=provider_label)
