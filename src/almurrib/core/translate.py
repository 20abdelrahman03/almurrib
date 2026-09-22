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
from almurrib.providers.prompts import build_messages as _build_prompt_messages


@dataclass
class TranslationStats:
    total: int = 0
    already_translated: int = 0
    memory_hits: int = 0
    cache_hits: int = 0
    api_calls: int = 0
    fallback_calls: int = 0  # individual requests after a malformed batch
    api_translated: int = 0
    # Accepted = parsed AND valid AND QA-clean AND staged for persistence.
    # This is the ONLY success metric the progress bar and health panel
    # may use — never requests sent, tokens spent, or HTTP 200s.
    accepted: int = 0
    rejected: int = 0
    requests: int = 0  # provider calls attempted (batches + fallback singles)
    retries: int = 0  # HTTP-level retries inside providers
    input_tokens: int = 0  # only when the provider reports usage
    output_tokens: int = 0  # only when the provider reports usage
    placeholder_failures: int = 0
    arabic_errors: int = 0  # entries FLAGGED by Arabic QA (non-placeholder)
    arabic_flags: int = 0  # total Arabic QA flags appended (any severity)
    glossary_flags: int = 0  # glossary QA flags appended (any severity)
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    first_error: str | None = None  # the first provider failure cause
    first_category: str | None = None  # taxonomy code for first_error
    first_http_status: int | None = None  # structured HTTP status, if known
    first_provider_message: str | None = None  # provider's own message, if any
    last_success: tuple[str, str] | None = None  # (source, translated) sample
    last_error: str | None = None
    last_category: str | None = None
    journal: list["BatchHealth"] = field(default_factory=list)  # capped


@dataclass
class BatchHealth:
    """One batch's full journey: sent → received → parsed → accepted."""

    batch_id: int = 0
    provider: str = ""
    model: str = ""
    entries: int = 0
    http_status: int | None = None
    latency_s: float = 0.0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    parsed: int = 0
    accepted: int = 0
    rejected: int = 0
    persisted: int = 0
    failure_category: str = ""
    first_error: str = ""

    @property
    def usable(self) -> bool:
        """Did this batch prove a working pipeline (parsed+persisted)?"""
        return self.parsed > 0 and self.persisted > 0


def classify_failure(exc: BaseException | None, message: str = "") -> str:
    """Map any failure to the human-readable taxonomy (§7 of the incident).

    Never returns empty: unknown causes are UNKNOWN_PROVIDER_ERROR, never
    a bare "Translation failed."
    """
    from almurrib.core.errors import (
        AuthenticationError,
        InvalidResponseError,
        ProviderTimeoutError,
        RateLimitError,
    )

    text = f"{exc} {message}" if exc is not None else message
    lowered = text.lower()
    if "quota" in lowered:
        return "QUOTA_EXCEEDED"
    if "timed out" in lowered or "timeout" in lowered:
        return "TIMEOUT"
    if isinstance(exc, AuthenticationError):
        return "AUTH_ERROR"
    if isinstance(exc, RateLimitError):
        return "QUOTA_EXCEEDED" if "quota" in lowered else "RATE_LIMIT"
    if isinstance(exc, ProviderTimeoutError):
        return "TIMEOUT"
    if "did not return a translation for entry" in text:
        return "WRONG_OUTPUT_COUNT"
    if "did not contain any requested ids" in text:
        return "ID_MAPPING_FAILURE"
    if "was not a json object" in lowered or "was not valid json" in lowered:
        return "INVALID_JSON"
    if "no reply text" in text or "empty" in lowered and "response" in lowered:
        return "EMPTY_RESPONSE"
    if isinstance(exc, InvalidResponseError):
        return "INVALID_PROVIDER_SCHEMA"
    if "placeholder" in lowered:
        return "PLACEHOLDER_MISMATCH"
    if "markup" in lowered or "tag" in lowered and "mismatch" in lowered:
        return "MARKUP_MISMATCH"
    if "qa" in lowered or "arabic" in lowered and "flag" in lowered:
        return "QA_REJECTION"
    if "persist" in lowered or "database" in lowered or "sqlite" in lowered:
        return "PERSISTENCE_FAILURE"
    if "http 404" in lowered or "not found" in lowered:
        return "HTTP_ERROR"
    if "http 429" in lowered:
        return "RATE_LIMIT"
    if "http 401" in lowered or "http 403" in lowered:
        return "AUTH_ERROR"
    if "http 5" in lowered:
        return "SERVER_ERROR"
    if "http" in lowered:
        return "HTTP_ERROR"
    if exc is None and "qa" in lowered:
        return "QA_REJECTION"
    return "UNKNOWN_PROVIDER_ERROR"


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
        abort_after_consecutive_failures: int = 5,
        # Token-waste ceiling: output tokens spent with zero accepted
        # translations before aborting. Basis: the incident burned ~125
        # output tokens per dead entry; 50_000 ≈ 400 dead entries or ~12
        # clean batches — generous, catches only true blackouts. None
        # disables (dormant when providers report no usage either way).
        max_wasted_output_tokens: int | None = 50_000,
        sample_every: int = 50,
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
        self.abort_after_consecutive_failures = abort_after_consecutive_failures
        self.max_wasted_output_tokens = max_wasted_output_tokens
        self.sample_every = max(1, sample_every)

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
        progress=None,  # optional callable(accepted: int, total: int)
        log=None,  # optional callable(message: str) for milestone lines
    ) -> TranslationStats:
        # Obsolete entries vanished from source: never translate, never count,
        # so progress and totals stay exact across repeated runs.
        entries = [e for e in entries if e.status is not EntryStatus.OBSOLETE]
        stats = TranslationStats(total=len(entries))
        pending: list[LocalizationEntry] = []

        def count_accepted() -> None:
            # Skip-path hits (already/TM/cache) are accepted work: they
            # needed no provider call and persist at the end with the rest.
            stats.accepted += 1
            if progress is not None:
                progress(stats.accepted, stats.total)

        identity = self.provider.config.identity
        for entry in entries:
            if entry.translated_text and not self.force:
                stats.already_translated += 1
                # Recomputed deterministically so flags always describe the
                # current text (self-healing across runs and rule updates).
                self._apply_qa(entry, entry.translated_text,
                               target_lang=target_lang, stats=stats, reset=False)
                count_accepted()
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
                    count_accepted()
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
                    count_accepted()
                    continue

            pending.append(entry)

        # 3. provider batch translation for what is left
        if pending:
            self._translate_pending(
                pending, source_lang, target_lang, stats,
                progress=progress,
                log=log,
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
        log=None,
    ) -> None:
        """Translate one provider-bound remainder with full observability.

        Per-chunk contract (§1 of the incident): every batch records a
        BatchHealth journey (sent → HTTP → parsed → accepted → persisted)
        and emits bounded milestone log lines. Progress advances ONLY on
        accepted translations (report clean AND QA clean AND staged);
        failures surface as [ALERT] lines and counts, never as progress.
        """
        import time as _time

        batch_size = max(1, self.provider.config.batch_size)
        total = stats.total
        n_batches = (len(entries) + batch_size - 1) // max(batch_size, 1)
        accepted_cum = stats.accepted
        failed_streak = 0
        wasted_output = 0
        identity = f"{self.provider.config.provider}:{self.provider.config.model}"

        def emit(message: str) -> None:
            if log is not None:
                log(message)

        for batch_id, start in enumerate(range(0, len(entries), batch_size), 1):
            chunk = entries[start : start + batch_size]
            requests = [self._build_request(e, source_lang, target_lang)
                        for e in chunk]
            by_id = {e.id: e for e in chunk}
            health = BatchHealth(
                batch_id=batch_id,
                provider=self.provider.config.provider,
                model=self.provider.config.model,
                entries=len(chunk),
            )
            emit(f"[TRANSLATE] Batch {batch_id}/{n_batches} — "
                 f"sending {len(chunk)} entries ({identity})...")
            t0 = _time.monotonic()
            try:
                results = self.provider.translate_batch(requests)
                stats.api_calls += 1
                stats.requests += 1
                fallback_n = int(
                    getattr(self.provider, "last_fallback_calls", 0) or 0)
                stats.fallback_calls += fallback_n
                stats.retries += fallback_n  # observable retry signal
                stats.requests += fallback_n
            except Exception as exc:  # provider errors already stage-tagged
                health.latency_s = round(_time.monotonic() - t0, 2)
                health.http_status = getattr(exc, "http_status", None)
                health.failure_category = classify_failure(exc)
                health.first_error = str(exc)[:300]
                # Usage still counts: failed HTTP calls may have generated
                # output (unparsable bodies) before raising.
                chunk_usage = getattr(self.provider, "last_usage", None)
                if chunk_usage:
                    health.input_tokens, health.output_tokens = chunk_usage
                    stats.input_tokens += chunk_usage[0]
                    stats.output_tokens += chunk_usage[1]
                    wasted_output += chunk_usage[1]
                    if (self.max_wasted_output_tokens is not None
                            and wasted_output >= self.max_wasted_output_tokens):
                        from almurrib.core.errors import TranslationAbortedError

                        self._record_batch(stats, health)
                        raise TranslationAbortedError(
                            f"aborted: {wasted_output} output tokens spent "
                            f"with zero accepted translations "
                            f"({stats.failed} failed of {total})",
                            hint="the provider answers but nothing is usable — "
                                 "check model output format, then re-run.",
                        ) from exc
                self._record_batch(stats, health)
                stats.failed += len(chunk)
                stats.errors.append(str(exc))
                stats.last_error = str(exc)[:300]
                stats.last_category = health.failure_category
                # Surface the first real cause instead of silently counting.
                if stats.first_error is None:
                    from almurrib.core.errors import ProviderError

                    stats.first_error = str(exc)
                    stats.first_category = health.failure_category
                    if isinstance(exc, ProviderError):
                        stats.first_http_status = exc.http_status
                        stats.first_provider_message = exc.provider_message
                emit(f"[ALERT] Batch {batch_id}/{n_batches} produced ZERO "
                     f"accepted translations.")
                emit(f"[ALERT] Category: {health.failure_category} | "
                     f"HTTP: {health.http_status} | "
                     f"Reason: {health.first_error}")
                emit(f"[ALERT] Consecutive zero-accept batches: "
                     f"{failed_streak + 1}/{self.abort_after_consecutive_failures}")
                # Circuit breaker: consecutive batches with zero ACCEPTED
                # translations mean the run cannot succeed — abort instead
                # of burning the remaining thousands.
                failed_streak += 1
                if failed_streak >= self.abort_after_consecutive_failures:
                    from almurrib.core.errors import TranslationAbortedError

                    raise TranslationAbortedError(
                        f"aborted after {failed_streak} consecutive batches "
                        f"with zero accepted translations "
                        f"({stats.failed} failed of {total}); "
                        f"first cause [{stats.first_category}]: "
                        f"{stats.first_error}",
                        hint="fix the provider/model/key, then re-run — "
                             "untouched entries stay untranslated and retryable.",
                    ) from exc
                continue

            health.latency_s = round(_time.monotonic() - t0, 2)
            health.http_status = getattr(
                self.provider, "last_http_status", None)
            usage = getattr(self.provider, "last_usage", None)
            if usage:
                health.input_tokens, health.output_tokens = usage
                stats.input_tokens += usage[0]
                stats.output_tokens += usage[1]
            health.parsed = len({res.entry_id for res in results})
            returned_ids = {res.entry_id for res in results}
            chunk_accepted = 0
            for res in results:
                entry = by_id.get(res.entry_id)
                if entry is None:
                    continue
                # Canonical stored text: NFC-normalized (lossless), never
                # shaped/reordered — render-ready forms derive on demand.
                from almurrib.arabic.normalize import normalize_text

                text = normalize_text(res.translated_text)
                if not text.strip():
                    # EMPTY_TRANSLATION (§2: non-empty output is required).
                    entry.translated_text = text
                    entry.status = EntryStatus.FLAGGED
                    entry.translation_provider = self.provider.config.provider
                    entry.translation_model = self.provider.config.model
                    entry.translation_source = TranslationSource.MACHINE.value
                    stats.api_translated += 1
                    stats.rejected += 1
                    stats.last_error = (
                        f"EMPTY_TRANSLATION: entry {entry.id}")[:300]
                    stats.last_category = "EMPTY_TRANSLATION"
                    continue
                report = validate_translation(entry.source_text, text)
                entry.translated_text = text
                entry.status = EntryStatus.TRANSLATED
                has_errors = self._apply_qa(
                    entry, text, target_lang=target_lang, stats=stats, reset=True)
                if not report.ok or has_errors:
                    entry.status = EntryStatus.FLAGGED
                    stats.rejected += 1
                    category = ("PLACEHOLDER_MISMATCH" if not report.ok
                                else classify_failure(None, "qa arabic flags"))
                    stats.last_error = (
                        f"{category}: entry {entry.id}")[:300]
                    stats.last_category = category
                else:
                    stats.accepted += 1
                    accepted_cum += 1
                    chunk_accepted += 1
                    stats.last_success = (
                        entry.source_text[:120], text[:120])
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
                    health.persisted += 1
                if progress is not None:
                    progress(accepted_cum, total)
                if (stats.accepted % self.sample_every == 0
                        and stats.accepted):
                    emit(f"[TRANSLATE] #{entry.id} "
                         f"EN: {entry.source_text[:100]!r} "
                         f"AR: {text[:100]!r}")

            # A partial batch must not silently drop entries: anything the
            # provider did not return stays untranslated AND is counted.
            for missing_id, missing_entry in by_id.items():
                if missing_id not in returned_ids and not missing_entry.translated_text:
                    # failed = nothing produced (stays pending). rejected is
                    # reserved for produced-but-refused output (disjoint).
                    stats.failed += 1
                    stats.errors.append(
                        f"provider did not return a translation for entry {missing_id}"
                    )
                    stats.last_error = stats.errors[-1][:300]
                    stats.last_category = "WRONG_OUTPUT_COUNT"
            health.rejected = len(chunk) - chunk_accepted
            health.accepted = chunk_accepted

            if chunk_accepted:
                failed_streak = 0
                wasted_output = 0
                emit(f"[PARSE] outputs={health.parsed} "
                     f"[VALIDATE] accepted={chunk_accepted} "
                     f"rejected={health.rejected} "
                     f"[PERSIST] saved={health.persisted} "
                     f"[PROGRESS] {accepted_cum}/{total}")
            else:
                emit(f"[ALERT] Batch {batch_id}/{n_batches} produced ZERO "
                     f"accepted translations.")
                emit(f"[ALERT] HTTP: {health.http_status} | "
                     f"Parsed: {health.parsed}/{len(chunk)} | "
                     f"Latency: {health.latency_s}s")
                failed_streak += 1
                # Token-waste rule: output tokens spent with zero accepted
                # output must stay bounded even when the provider keeps
                # answering (the incident signature). Inactive when the
                # provider reports no usage.
                wasted_output += health.output_tokens
                if (self.max_wasted_output_tokens is not None
                        and wasted_output >= self.max_wasted_output_tokens):
                    from almurrib.core.errors import TranslationAbortedError

                    raise TranslationAbortedError(
                        f"aborted: {wasted_output} output tokens spent with "
                        f"zero accepted translations "
                        f"({stats.failed} failed of {total})",
                        hint="the provider answers but nothing is usable — "
                             "check model output format, then re-run.",
                    )
                if failed_streak >= self.abort_after_consecutive_failures:
                    from almurrib.core.errors import TranslationAbortedError

                    raise TranslationAbortedError(
                        f"aborted after {failed_streak} consecutive batches "
                        f"with zero accepted translations "
                        f"({stats.failed} failed of {total}); "
                        f"first cause [{stats.first_category}]: "
                        f"{stats.first_error}",
                        hint="fix the provider/model/key, then re-run — "
                             "untouched entries stay untranslated and retryable.",
                    ) from None
            self._record_batch(stats, health)

    @staticmethod
    def _record_batch(stats: TranslationStats, health: BatchHealth) -> None:
        """Append to the bounded run journal (last 50 batches kept)."""
        stats.journal.append(health)
        if len(stats.journal) > 50:
            del stats.journal[:-50]


# ----- canary / preflight / health (§§3, 5, 12 of the incident) -----


@dataclass
class CanaryResult:
    """Outcome of the 3-entry provider gate before a large run."""

    passed: bool
    tested: int = 0
    accepted: int = 0
    provider: str = ""
    model: str = ""
    sample: tuple[str, str] | None = None
    error: str = ""
    category: str = ""


def run_canary(
    entries: list[LocalizationEntry],
    *,
    provider: TranslationProvider,
    source_lang: str = "en",
    target_lang: str = "ar",
    glossary: Glossary | None = None,
    count: int = 3,
    log=None,
    cache=None,
    memory=None,
) -> CanaryResult:
    """Prove the provider works BEFORE a large run spends tokens.

    Takes the first ``count`` pending entries and runs them through the
    REAL stage with ``force=True`` (bypasses TM/cache so a stale cache
    cannot fake a PASS). PASS requires every tested entry accepted;
    anything less blocks the full run with the exact cause.
    """
    from almurrib.core.model import EntryStatus as _Status

    candidates = [e for e in entries
                  if e.status is not _Status.OBSOLETE
                  and not e.translated_text][:count]
    identity = f"{provider.config.provider}:{provider.config.model}"
    if log is not None:
        log(f"[CANARY] Testing provider {identity} on "
            f"{len(candidates)} entries...")
    if not candidates:
        return CanaryResult(True, 0, 0, provider.config.provider,
                            provider.config.model)
    stage = RealTranslateStage(provider, glossary=glossary, force=True,
                                 cache=cache, memory=memory)
    try:
        stats = stage.run(candidates, source_lang=source_lang,
                          target_lang=target_lang, log=log)
    except Exception as exc:
        category = classify_failure(exc)
        if log is not None:
            log(f"[CANARY] FAIL — {category}: {exc}")
        return CanaryResult(False, len(candidates), 0,
                            provider.config.provider,
                            provider.config.model,
                            error=str(exc)[:300], category=category)
    accepted = stats.accepted
    sample = stats.last_success
    passed = accepted == len(candidates) and accepted > 0
    if log is not None:
        log(f"[CANARY] Parsed+accepted: {accepted}/{len(candidates)}")
        if sample is not None:
            log(f"[CANARY] Sample: {sample[0]!r} → {sample[1]!r}")
        log("[CANARY] PASS — starting full translation."
            if passed else
            "[CANARY] FAIL — full run blocked "
            f"(last error [{stats.last_category}]: {stats.last_error})")
    return CanaryResult(
        passed, len(candidates), accepted, provider.config.provider,
        provider.config.model, sample,
        error="" if passed else (stats.last_error or "no entries accepted"),
        category="" if passed else (stats.last_category or "UNKNOWN"),
    )


@dataclass
class TranslationHealth:
    """One compact snapshot for the live panel, log and CLI table."""

    provider: str = ""
    model: str = ""
    total: int = 0
    accepted: int = 0
    failed: int = 0
    rejected: int = 0
    batch: int = 0
    batches: int = 0
    consecutive_zero: int = 0
    requests: int = 0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    last_success: tuple[str, str] | None = None
    last_error: str = ""
    last_category: str = ""

    @property
    def pending(self) -> int:
        return max(0, self.total - self.accepted - self.failed)

    @property
    def acceptance_rate(self) -> float:
        decided = self.accepted + self.failed + self.rejected
        return (self.accepted / decided) if decided else 0.0


def health_snapshot(stats: TranslationStats, *, provider,
                    batch: int = 0, batches: int = 0,
                    consecutive_zero: int = 0) -> TranslationHealth:
    """Build a panel-ready snapshot from live stats (no I/O, no secrets)."""
    return TranslationHealth(
        provider=provider.config.provider, model=provider.config.model,
        total=stats.total, accepted=stats.accepted, failed=stats.failed,
        rejected=stats.rejected, batch=batch, batches=batches,
        consecutive_zero=consecutive_zero, requests=stats.requests,
        retries=stats.retries, input_tokens=stats.input_tokens,
        output_tokens=stats.output_tokens, last_success=stats.last_success,
        last_error=stats.last_error or "",
        last_category=stats.last_category or "",
    )


def render_health(health: TranslationHealth) -> list[str]:
    """Panel block lines (§5). Pure rendering, safe to call every batch."""
    lines = [
        "TRANSLATION HEALTH",
        f"Model: {health.model}",
        f"Progress: {health.accepted} / {health.total}",
        f"Accepted: {health.accepted}",
        f"Failed: {health.failed}",
        f"Pending: {health.pending}",
        f"Batch: {health.batch} / {health.batches}",
        "",
        f"Requests: {health.requests}",
        f"Retries: {health.retries}",
        f"Tokens: {health.input_tokens + health.output_tokens:,} "
        f"(in {health.input_tokens:,} / out {health.output_tokens:,})",
        f"Acceptance rate: {100.0 * health.acceptance_rate:.1f}%",
        "",
    ]
    if health.last_success is not None:
        lines.append(f"Last success: {health.last_success[0]!r} → "
                     f"{health.last_success[1]!r}")
    if health.last_error:
        lines.append(f"Last error [{health.last_category}]: {health.last_error}")
    if not health.last_success and health.requests and not health.accepted:
        lines.append("WARNING: requests are being sent but nothing is "
                     "being accepted.")
    return lines


@dataclass
class PreflightEstimate:
    """Dry-run numbers (§12). Token figures state their basis explicitly."""

    total: int = 0
    already: int = 0
    pending: int = 0
    provider: str = ""
    model: str = ""
    batches: int = 0
    est_input_tokens: int = 0
    est_output_tokens: int = 0
    token_basis: str = ""
    canary: CanaryResult | None = None


def estimate_preflight(
    entries: list[LocalizationEntry],
    *,
    provider: TranslationProvider,
    source_lang: str = "en",
    target_lang: str = "ar",
    glossary: Glossary | None = None,
    log=None,
) -> PreflightEstimate:
    """Count the job and measure prompt cost WITHOUT translating it.

    Token basis is MEASURED, not guessed: real requests are built for up
    to 5 sample entries and their character length ÷ 4 approximates
    tokens (documented heuristic for EN/AR text). Output ≈ 1.2× source
    tokens (Arabic runs near source length; 1.2 is margin, labeled).
    """
    from almurrib.core.model import EntryStatus as _Status

    total = len([e for e in entries if e.status is not _Status.OBSOLETE])
    already = len([e for e in entries if e.translated_text])
    pending_entries = [e for e in entries
                       if e.status is not _Status.OBSOLETE
                       and not e.translated_text]
    batch_size = max(1, provider.config.batch_size)
    batches = (len(pending_entries) + batch_size - 1) // batch_size
    # Measure: build real requests for a few samples, count characters.
    probe = RealTranslateStage(provider, glossary=glossary)
    sample_chars = 0
    sample_src_tokens = 0
    samples = pending_entries[:5]
    for entry in samples:
        req = probe._build_request(entry, source_lang, target_lang)
        prompt_chars = sum(len(m.get("content", "")) for m in
                           _build_prompt_messages([req]))
        sample_chars += prompt_chars
        sample_src_tokens += max(1, len(entry.source_text) // 4)
    if samples:
        per_entry_in = sample_chars // (4 * len(samples))
        per_entry_out = (sample_src_tokens * 6) // (5 * len(samples))
        basis = (f"measured from {len(samples)} real built requests "
                 f"(chars÷4 heuristic, output≈1.2× source)")
    else:
        per_entry_in = per_entry_out = 0
        basis = "no pending entries — nothing to estimate"
    estimate = PreflightEstimate(
        total=total, already=already, pending=len(pending_entries),
        provider=provider.config.provider, model=provider.config.model,
        batches=batches,
        est_input_tokens=per_entry_in * len(pending_entries),
        est_output_tokens=per_entry_out * len(pending_entries),
        token_basis=basis,
    )
    if log is not None:
        log(f"[PREFLIGHT] Entries: {total} | already: {already} | "
            f"pending: {estimate.pending}")
        log(f"[PREFLIGHT] Provider: {estimate.provider} "
            f"model: {estimate.model} | batches: ~{batches}")
        log(f"[PREFLIGHT] Est. tokens: in ~{estimate.est_input_tokens:,} / "
            f"out ~{estimate.est_output_tokens:,} ({basis})")
    return estimate
