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


from almurrib.core.glossary import Glossary, build_translation_context
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
    arabic_errors: int = 0  # entries FLAGGED by Arabic QA (non-placeholder)
    arabic_flags: int = 0  # total Arabic QA flags appended (any severity)
    glossary_flags: int = 0  # glossary QA flags appended (any severity)
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
        glossary: Glossary | None = None,
    ) -> None:
        """Force semantics: ignore already-translated text, TM and cache
        reads; the provider is called again and provenance is overwritten.
        ``reuse_machine_tm`` permits cross-model reuse of machine TM
        (default False: same provider:model or human/imported only).
        ``glossary`` guides providers via prompt context and enforces
        terminology through QA (never by blind post-replacement).
        """
        self.provider = provider
        self.cache = cache
        self.memory = _MemoryView(memory or {})
        self.force = force
        self.reuse_machine_tm = reuse_machine_tm
        self.glossary = glossary

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
                # Recomputed deterministically so flags always describe the
                # current text (self-healing across runs and rule updates).
                self._apply_qa(entry, entry.translated_text,
                               target_lang=target_lang, stats=stats, reset=False)
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
                ) and not self._glossary_veto(entry, tm_hit.text):
                    entry.translated_text = tm_hit.text
                    entry.translation_source = tm_hit.source
                    entry.translation_provider = (
                        tm_hit.provider.split(":")[0] if tm_hit.provider else None
                    )
                    entry.translation_model = tm_hit.model
                    entry.status = EntryStatus.TRANSLATED
                    self._apply_qa(entry, tm_hit.text,
                                   target_lang=target_lang, stats=stats, reset=False)
                    stats.memory_hits += 1
                    done += 1
                    tick()
                    continue

            # 2. cache (provider+model+lang specific, skipped under force)
            if self.cache is not None and not self.force:
                record = self.cache.lookup(entry)
                if (record is not None and record.translated_text
                        and not self._glossary_veto(entry, record.translated_text)):
                    entry.translated_text = record.translated_text
                    entry.status = EntryStatus.TRANSLATED
                    self._apply_qa(entry, record.translated_text,
                                   target_lang=target_lang, stats=stats, reset=False)
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

    # Machine states QA themselves; human REVIEWED/APPROVED states are
    # sacred and never touched by automatic QA.
    _QAABLE_STATES = (EntryStatus.UNTRANSLATED, EntryStatus.TRANSLATED,
                      EntryStatus.FLAGGED)

    def _glossary_veto(self, entry: LocalizationEntry, text: str) -> bool:
        """True when the current glossary rejects a TM/cache candidate.

        Fine-grained invalidation: only entries whose cached text violates
        the ACTIVE glossary fall through to the provider; unrelated entries
        keep their hits. No glossary (or no matches) never vetoes.
        """
        if self.glossary is None:
            return False
        from almurrib.core.glossary import glossary_qa_check

        matches = self.glossary.lookup(entry.source_text)
        if not matches:
            return False
        # Any glossary finding (error OR warning) vetoes the hit: a stale
        # cached text that no longer satisfies the active glossary must be
        # retranslated, not quietly reused.
        return any(f.rule_id.startswith("glossary.")
                   for f in glossary_qa_check(entry.source_text, text, matches))

    def _apply_qa(self, entry: LocalizationEntry, text: str, *,
                  target_lang: str, stats: TranslationStats,
                  reset: bool) -> bool:
        """(Re)compute QA flags for machine-state text. Returns has-errors.

        ``reset`` drops existing flags first (fresh API translation).
        Otherwise new tokens merge without duplicating (stable re-runs).
        An error upgrades TRANSLATED to FLAGGED; nothing else moves status.
        """
        if entry.status not in self._QAABLE_STATES:
            return False
        from almurrib.arabic.qa import arabic_qa_check
        from almurrib.core.glossary import glossary_qa_check

        if reset:
            entry.qa_flags = []
        fresh = arabic_qa_check(entry.source_text, text,
                                target_lang=target_lang, entry_id=entry.id)
        glossary_flags: list = []
        if self.glossary is not None:
            matches = self.glossary.lookup(entry.source_text)
            glossary_flags = glossary_qa_check(
                entry.source_text, text, matches)
            fresh.flags.extend(glossary_flags)
        new_tokens = [f.storage_token() for f in fresh.flags
                      if f.storage_token() not in entry.qa_flags]
        entry.qa_flags.extend(new_tokens)
        new_glossary = sum(
            1 for f in glossary_flags
            if f.storage_token() in new_tokens)
        stats.glossary_flags += new_glossary
        stats.arabic_flags += len(new_tokens) - new_glossary
        errors = [f for f in fresh.flags if f.severity == "error"]
        if errors:
            if any(f.rule_id == "placeholder_missing" for f in errors):
                stats.placeholder_failures += 1
            if any(f.rule_id != "placeholder_missing"
                   and not f.rule_id.startswith("glossary.") for f in errors):
                stats.arabic_errors += 1
            if entry.status is EntryStatus.TRANSLATED:
                entry.status = EntryStatus.FLAGGED
        return bool(errors)

    def _build_request(self, entry: LocalizationEntry, source_lang: str,
                       target_lang: str) -> TranslationRequest:
        """One provider request enriched with glossary/speaker context."""
        context = build_translation_context(entry, self.glossary)
        return TranslationRequest(
            entry_id=entry.id,
            source_text=entry.source_text,
            source_lang=source_lang,
            target_lang=target_lang,
            speaker=entry.speaker,
            context=entry.context,
            placeholders=extract_placeholders(entry.source_text),
            speaker_gender=context.speaker_gender,
            speaker_style=context.speaker_style,
            glossary_terms=context.glossary_terms,
        )

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
            requests = [self._build_request(e, source_lang, target_lang)
                        for e in chunk]
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
                # Canonical stored text: NFC-normalized (lossless), never
                # shaped/reordered — render-ready forms derive on demand.
                from almurrib.arabic.normalize import normalize_text

                text = normalize_text(res.translated_text)
                report = validate_translation(entry.source_text, text)
                entry.translated_text = text
                entry.status = EntryStatus.TRANSLATED
                has_errors = self._apply_qa(
                    entry, text, target_lang=target_lang, stats=stats, reset=True)
                if not report.ok or has_errors:
                    entry.status = EntryStatus.FLAGGED
                entry.translation_provider = self.provider.config.provider
                entry.translation_model = self.provider.config.model
                entry.translation_source = TranslationSource.MACHINE.value
                stats.api_translated += 1
                if report.ok and self.cache is not None:
                    # Broken translations are persisted as FLAGGED for review
                    # but must never poison the cache as good translations.
                    # Cache the NORMALIZED text: it must equal what the entry
                    # (and later cache hits) carry, or runs diverge.
                    self.cache.remember(entry, text)
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
