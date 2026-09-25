"""Translation pipeline safety tests (incident §14).

Covers the full failure taxonomy: HTTP-200-but-useless responses,
zero-success batches, breaker behavior, token-waste rule, persistence
semantics, cache safety, canary gating and the Hollow Knight replay.
All deterministic (scripted providers, no network).
"""

import pytest

from almurrib.core.errors import TranslationAbortedError
from almurrib.core.model import EngineType, EntryStatus, LocalizationEntry, SourceRef
from almurrib.core.provider import ProviderConfig, TranslationResult
from almurrib.core.translate import (
    RealTranslateStage,
    classify_failure,
    health_snapshot,
    render_health,
    run_canary,
)
from almurrib.providers.fake import FakeProvider
from tests.conftest import ArabicStubProvider


def _entry(text, line):
    ref = SourceRef(file="game/script.rpy", line=line)
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, text, ref),
        engine=EngineType.RENPY, source_text=text,
        source_refs=[ref], status=EntryStatus.UNTRANSLATED)


class _ScriptedProvider:
    """Deterministic provider: scripted behavior per batch + usage."""

    def __init__(self, behavior, *, usage=(0, 0), batch_size=20):
        self._behavior = behavior
        self.calls = 0
        self.last_usage = None
        self._usage = usage
        self.last_http_status = 200
        self.last_fallback_calls = 0
        self._config = ProviderConfig(
            provider="scripted", model="test-1",
            base_url="http://localhost.invalid", api_key="x",
            batch_size=batch_size)

    @property
    def config(self):
        return self._config

    def capabilities(self):
        from almurrib.core.provider import ProviderCapabilities

        return ProviderCapabilities(supports_batch=True)

    def translate_batch(self, requests):
        self.calls += 1
        self.last_usage = self._usage
        return self._behavior(requests)


def _arabic_mapping(requests):
    return [TranslationResult(
        entry_id=r.entry_id, translated_text=f"ترجمة عربية: {r.source_text}",
        provider="scripted", model="test-1") for r in requests]


def _run(entries, provider, **kwargs):
    kwargs.setdefault("target_lang", "ar")
    return RealTranslateStage(provider).run(entries, **kwargs)


# 1. HTTP 200 + valid translations → accepted ------------------------------
def test_valid_batch_accepted_and_counted():
    entries = [_entry(f"line {i}", i) for i in range(3)]
    stats = _run(entries, _ScriptedProvider(_arabic_mapping))
    assert stats.accepted == 3 and stats.rejected == 0 and stats.failed == 0
    assert all(e.status is EntryStatus.TRANSLATED for e in entries)
    assert stats.last_success is not None


# 2/3. empty / malformed responses → rejected, nothing accepted -------------
@pytest.mark.parametrize("behavior", [
    pytest.param(lambda reqs: (_ for _ in ()).throw(
        __import__("almurrib.core.errors", fromlist=["InvalidResponseError"])
        .InvalidResponseError("empty response")), id="empty"),
    pytest.param(lambda reqs: (_ for _ in ()).throw(
        __import__("almurrib.core.errors", fromlist=["InvalidResponseError"])
        .InvalidResponseError("model output was not a JSON object: 'oops'")),
        id="malformed"),
])
def test_unparsable_batch_rejected(behavior):
    entries = [_entry(f"line {i}", i) for i in range(3)]
    stats = _run(entries, _ScriptedProvider(behavior))
    assert stats.accepted == 0 and stats.failed == 3
    assert all(e.translated_text is None for e in entries)  # still pending


# 4/6. wrong count / empty translations → partial failure, rest accepted ----
def test_partial_batch_counts_missing_as_failed():
    entries = [_entry(f"line {i}", i) for i in range(3)]

    def partial(requests):
        return _arabic_mapping(requests[:2])  # third id missing

    stats = _run(entries, _ScriptedProvider(partial))
    assert stats.accepted == 2 and stats.failed == 1
    assert entries[2].translated_text is None


def test_empty_translation_strings_rejected():
    entries = [_entry(f"line {i}", i) for i in range(2)]

    def empty(requests):
        from almurrib.core.provider import TranslationResult as TR

        return [TR(entry_id=requests[0].entry_id, translated_text="",
                   provider="s", model="t")]

    stats = _run(entries, _ScriptedProvider(empty))
    assert stats.accepted == 0 and stats.rejected == 1 and stats.failed == 1
    assert entries[0].status is EntryStatus.FLAGGED  # empty → rejected, kept


# 5. invalid IDs → rejected -------------------------------------------------
def test_wrong_ids_rejected():
    entries = [_entry(f"line {i}", i) for i in range(2)]

    def wrong_ids(requests):
        from almurrib.core.provider import TranslationResult as TR

        return [TR(entry_id="nope-1", translated_text="ترجمة",
                   provider="s", model="t")]

    stats = _run(entries, _ScriptedProvider(wrong_ids))
    assert stats.accepted == 0 and stats.failed == 2


# 7. placeholder mismatch → FLAGGED, rejected, never cached ------------------
def test_placeholder_mismatch_flagged_not_accepted():
    entries = [_entry("{name} welcome home", 1)]

    def drop_token(requests):
        from almurrib.core.provider import TranslationResult as TR

        return [TR(entry_id=requests[0].entry_id,
                   translated_text="أهلا بك في البيت",  # {name} lost
                   provider="s", model="t")]

    from almurrib.core.cache import TranslationCache

    cache = TranslationCache(target_lang="ar", provider="scripted:test-1")
    stage = RealTranslateStage(_ScriptedProvider(drop_token), cache=cache)
    stats = stage.run(entries, target_lang="ar")
    assert stats.accepted == 0 and stats.rejected == 1
    assert entries[0].status is EntryStatus.FLAGGED
    assert len(cache) == 0, "broken output must never poison the cache"


# 8. all rejected → zero-success batch (alert, no abort under threshold) ----
def test_all_rejected_batch_alerts_without_abort():
    entries = [_entry(f"line {i}", i) for i in range(3)]
    lines: list[str] = []
    stats = _run(entries, FakeProvider(), log=lines.append)
    assert stats.accepted == 0
    assert any("ZERO" in line for line in lines)


# 11. token waste without acceptance → safety stop --------------------------
def test_token_waste_rule_stops_blackout():
    from almurrib.core.errors import InvalidResponseError

    def burn(requests):
        raise InvalidResponseError("model output was not a JSON object")

    provider = _ScriptedProvider(burn, usage=(5000, 30000))
    stage = RealTranslateStage(provider, max_wasted_output_tokens=50_000)
    entries = [_entry(f"line {i}", i) for i in range(200)]
    with pytest.raises(TranslationAbortedError, match="output tokens spent"):
        stage.run(entries, target_lang="ar")
    assert provider.calls < 10, "must stop early, not after 200 entries"


# 12/13. persistence semantics ----------------------------------------------
def test_success_persists_and_failure_stays_pending():
    entries = [_entry("hello world", 1), _entry("line 2", 2)]

    def one_good(requests):
        return _arabic_mapping(requests[:1])

    stats = _run(entries, _ScriptedProvider(one_good))
    assert entries[0].translated_text is not None
    assert entries[0].status is EntryStatus.TRANSLATED
    assert entries[1].translated_text is None
    assert entries[1].status is EntryStatus.UNTRANSLATED
    assert (stats.accepted, stats.failed) == (1, 1)


# 17. progress advances across batches during a live multi-batch run --------
def test_progress_advances_per_accepted_entry_across_batches():
    entries = [_entry(f"line {i}", i) for i in range(45)]
    seen: list[tuple[int, int]] = []
    stats = _run(entries, _ScriptedProvider(_arabic_mapping),
                 progress=lambda d, t: seen.append((d, t)))
    assert stats.accepted == 45
    assert len(seen) == 45 and seen[-1] == (45, 45)
    assert [d for d, _ in seen] == list(range(1, 46))


# 18/19. canary gate ---------------------------------------------------------
def test_canary_pass_allows_run():
    entries = [_entry(f"line {i}", i) for i in range(10)]
    lines: list[str] = []
    result = run_canary(entries, provider=ArabicStubProvider(), log=lines.append)
    assert result.passed and result.accepted == 3 and result.tested == 3
    assert any("PASS" in line for line in lines)
    assert any("→" in line for line in lines)  # sample shown


def test_canary_fail_blocks_run():
    from almurrib.core.errors import InvalidResponseError

    entries = [_entry(f"line {i}", i) for i in range(10)]
    result = run_canary(entries,
                        provider=_ScriptedProvider(
                            lambda reqs: (_ for _ in ()).throw(
                                InvalidResponseError("model output broken"))))
    assert not result.passed and result.accepted == 0


# 22. abort exposes the first representative cause ---------------------------
def test_abort_message_carries_category_and_cause():
    from almurrib.core.errors import ProviderError

    class Down:
        calls = 0

        @property
        def config(self):
            return ProviderConfig(provider="s", model="t",
                                  base_url="http://x.invalid", api_key="x")

        def capabilities(self):
            from almurrib.core.provider import ProviderCapabilities

            return ProviderCapabilities(supports_batch=True)

        def translate_batch(self, requests):
            Down.calls += 1
            raise ProviderError("model or endpoint not found (HTTP 404)",
                                http_status=404)

    stage = RealTranslateStage(Down())
    with pytest.raises(TranslationAbortedError) as info:
        stage.run([_entry(f"line {i}", i) for i in range(101)],
                  target_lang="ar")
    assert "5 consecutive" in str(info.value)
    assert "404" in str(info.value)
    assert Down.calls == 5, "zero batches may run after the breaker"


# Hollow Knight replay: 537 cached, dead provider, bounded abort --------------
def test_hk_replay_stops_safely_and_keeps_cache():
    """§14.20/21: the incident, replayed deterministically at small scale."""
    from almurrib.core.workflow import translate_entries
    from almurrib.storage.database import Database
    import tempfile
    from pathlib import Path

    from almurrib.core.errors import InvalidResponseError

    tmp = Path(tempfile.mkdtemp())

    def build(n):
        return [_entry(f"hollow knight line {i}", i) for i in range(n)]

    with Database(tmp / "hk.db") as db:
        conn = db.connection
        # Run 1 (healthy era): first 537 accepted and cached.
        stats1 = translate_entries(build(537), db, ArabicStubProvider())
        assert stats1.accepted == 537
        cached_rows = conn.execute(
            "select count(*) from translation_cache").fetchone()[0]
        assert cached_rows == 537

        # Run 2 (dead era): all 700 fresh objects, provider returns garbage.
        class Dead:
            calls = 0

            @property
            def config(self):
                return ProviderConfig(provider="dead", model="m",
                                      base_url="http://x.invalid", api_key="x")

            def capabilities(self):
                from almurrib.core.provider import ProviderCapabilities

                return ProviderCapabilities(supports_batch=True)

            def translate_batch(self, requests):
                Dead.calls += 1
                raise InvalidResponseError("model output was not a JSON object")

        with pytest.raises(TranslationAbortedError):
            translate_entries(build(700), db, Dead(), canary=False)
        # Breaker tripped at 5 chunks: 100 failed, 63 untouched, cache intact.
        assert Dead.calls == 5, "zero batches may run after the breaker"
        assert conn.execute(
            "select count(*) from translation_cache").fetchone()[0] == 537


def test_rerun_uses_cache_without_resending():
    """§14.14: successes are never re-requested."""
    from almurrib.core.workflow import translate_entries
    from almurrib.storage.database import Database
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())

    class Counting(ArabicStubProvider):
        calls = 0

        def translate_batch(self, requests):
            Counting.calls += 1
            return super().translate_batch(requests)

    def build(n):
        return [_entry(f"rerun line {i}", i) for i in range(30)]

    with Database(tmp / "r.db") as db:
        s1 = translate_entries(build(30), db, Counting())
        assert s1.accepted == 30 and Counting.calls == 2
        Counting.calls = 0
        s2 = translate_entries(build(30), db, Counting())
        assert Counting.calls == 0, "cache hits must not touch the provider"
        assert s2.accepted == 30


def test_dry_run_spends_only_canary():
    """§12: preflight counts + estimates + gates, without translating."""
    from almurrib.core.workflow import dry_run_report
    from almurrib.storage.database import Database
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())

    class Counting(ArabicStubProvider):
        calls = 0

        def translate_batch(self, requests):
            Counting.calls += 1
            return super().translate_batch(requests)

    with Database(tmp / "d.db") as db:
        estimate = dry_run_report(
            [_entry(f"dry line {i}", i) for i in range(120)],
            db, Counting())
    assert (estimate.total, estimate.pending, estimate.batches) == (120, 120, 6)
    assert estimate.est_input_tokens > 0 and estimate.est_output_tokens > 0
    assert "measured" in estimate.token_basis
    assert estimate.canary is not None and estimate.canary.passed
    assert Counting.calls == 1, "dry run spends exactly the canary batch"


# Dedup §§15-16: canonical source + occurrence fan-out -------------------------
def _dup_entry(text, line, context="ctx:same"):
    ref = SourceRef(file="game/script.rpy", line=line)
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, text, ref),
        engine=EngineType.RENPY, source_text=text, context=context,
        source_refs=[ref], status=EntryStatus.UNTRANSLATED)


def test_identical_strings_translate_once_and_fan_out():
    """37× 'New Game' → 1 provider call, 37 identical translations."""
    from tests.conftest import ArabicStubProvider

    class Counting(ArabicStubProvider):
        calls = 0

        def translate_batch(self, requests):
            Counting.calls += 1
            return super().translate_batch(requests)

    entries = [_dup_entry("New Game", i) for i in range(37)]
    ids_before = [e.id for e in entries]
    stats = _run(entries, Counting())
    assert Counting.calls == 1, "one canonical request per fingerprint group"
    assert stats.accepted == 37
    assert stats.unique_groups == 1
    assert stats.duplicate_occurrences == 36
    assert len({e.translated_text for e in entries}) == 1
    assert [e.id for e in entries] == ids_before, "ids/refs never rewritten"
    assert {e.source_refs[0].line for e in entries} == set(range(37))


def test_same_source_conflicting_context_translates_separately():
    """§16: same text, different context → separate groups, separate calls."""
    from tests.conftest import ArabicStubProvider

    class Counting(ArabicStubProvider):
        calls = 0

        def translate_batch(self, requests):
            Counting.calls += 1
            return super().translate_batch(requests)

    entries = ([_dup_entry("Charge!", i, context="ctx:battle") for i in range(3)]
               + [_dup_entry("Charge!", i + 10, context="ctx:payment")
                   for i in range(3)])
    stats = _run(entries, Counting())
    assert stats.unique_groups == 2
    assert stats.duplicate_occurrences == 4
    assert stats.accepted == 6
    # One batch of 2 representatives (batch_size 20) — but two groups sent.
    assert Counting.calls == 1


def test_canary_probes_distinct_fingerprints():
    """Canary over 3 copies of one string probes distinct sources."""
    from almurrib.core.translate import unique_representatives

    entries = ([_dup_entry("Same", i) for i in range(5)]
               + [_dup_entry("Other", 10), _dup_entry("Third", 11)])
    probe = unique_representatives(entries, 3)
    assert [e.source_text for e in probe] == ["Same", "Other", "Third"]


def test_fanout_survives_mid_run_abort():
    """Abort strands no completed occurrence: fan-out is immediate."""
    from almurrib.core.errors import TranslationAbortedError

    seen_calls = []

    class Flaky:
        @property
        def config(self):
            return ProviderConfig(provider="s", model="t",
                                  base_url="http://x.invalid", api_key="x")

        def capabilities(self):
            from almurrib.core.provider import ProviderCapabilities

            return ProviderCapabilities(supports_batch=True)

        def translate_batch(self, requests):
            seen_calls.append(len(requests))
            if len(seen_calls) == 1:
                return _arabic_mapping(requests)
            from almurrib.core.errors import InvalidResponseError

            raise InvalidResponseError("model output was not a JSON object")

    # 25 identical entries (1 group) + 90 unique → chunk1 succeeds for all
    # 25, then failures abort; the 25 occurrences must all be translated.
    entries = ([_dup_entry("Shared line", i) for i in range(25)]
               + [_dup_entry(f"solo {i}", 100 + i) for i in range(90)])
    stage = RealTranslateStage(Flaky(), abort_after_consecutive_failures=5)
    try:
        stage.run(entries, target_lang="ar")
    except TranslationAbortedError:
        pass
    shared = entries[:25]
    assert all(e.translated_text is not None for e in shared)


# Stop / pause / crash-recovery §§29-30 -----------------------------------------
def test_stop_event_halts_gracefully_with_partial_results():
    """Stop finishes the current chunk, persists it, leaves rest pending."""
    import threading

    from tests.conftest import ArabicStubProvider

    stop = threading.Event()
    saved: list = []
    entries = [_entry(f"stop line {i}", i) for i in range(60)]

    def persist(chunk):
        saved.extend(chunk)
        if len(saved) >= 40:
            stop.set()

    stats = _run(entries, ArabicStubProvider(), persist=persist,
                 stop_event=stop)
    assert stats.stopped is True
    assert stats.accepted == 40
    assert len(saved) == 40
    assert sum(1 for e in entries if e.translated_text) == 40
    assert sum(1 for e in entries if not e.translated_text) == 20


def test_pause_blocks_then_resumes():
    """Pause waits mid-run; resume completes everything."""
    import threading
    import time

    from tests.conftest import ArabicStubProvider

    pause = threading.Event()
    pause.set()
    entries = [_entry(f"pause line {i}", i) for i in range(25)]

    def release():
        time.sleep(0.6)
        pause.clear()

    threading.Thread(target=release, daemon=True).start()
    t0 = time.monotonic()
    stats = _run(entries, ArabicStubProvider(), pause_event=pause)
    assert time.monotonic() - t0 >= 0.5, "must actually have waited"
    assert stats.accepted == 25 and not stats.stopped


def test_crash_keeps_completed_chunks_via_persist():
    """KeyboardInterrupt mid-run loses nothing already persisted."""
    from tests.conftest import ArabicStubProvider

    persisted: list = []
    entries = [_entry(f"crash line {i}", i) for i in range(60)]

    def persist(chunk):
        persisted.extend(chunk)
        if len(persisted) >= 40:
            raise KeyboardInterrupt("simulated crash")

    with pytest.raises(KeyboardInterrupt):
        _run(entries, ArabicStubProvider(), persist=persist)
    assert len(persisted) == 40
    assert all(e.translated_text for e in persisted)


def test_resume_continues_from_persisted_prefix():
    """Stop + rerun: cache hits cover the prefix, provider does the rest."""
    from almurrib.core.workflow import translate_entries
    from almurrib.storage.database import Database
    import tempfile
    import threading
    from pathlib import Path

    from tests.conftest import ArabicStubProvider

    tmp = Path(tempfile.mkdtemp())

    class Counting(ArabicStubProvider):
        calls = 0

        def translate_batch(self, requests):
            Counting.calls += 1
            return super().translate_batch(requests)

    def build(n):
        return [_entry(f"resume line {i}", i) for i in range(n)]

    with Database(tmp / "rs.db") as db:
        from almurrib.storage.repository import EntryRepository

        repo = EntryRepository(db)
        project = repo.ensure_project("rs", str(tmp), EngineType.RENPY)
        stop = threading.Event()

        def on_progress(done, total):
            if done >= 40:
                stop.set()

        s1 = translate_entries(build(60), db, Counting(), project_id=project.id,
                               stop_event=stop, progress=on_progress)
        assert s1.stopped is True and s1.accepted == 40
        Counting.calls = 0
        s2 = translate_entries(build(60), db, Counting(), project_id=project.id)
        assert Counting.calls == 1, "only the 20 missing need the provider"
        assert s2.accepted == 60  # 40 cache + 20 fresh


# taxonomy unit checks ---------------------------------------------------------
@pytest.mark.parametrize("exc_msg,category", [
    ("invalid key (HTTP 401)", "AUTH_ERROR"),
    ("rate limit (HTTP 429)", "RATE_LIMIT"),
    ("quota exceeded (HTTP 429)", "QUOTA_EXCEEDED"),
    ("timed out", "TIMEOUT"),
    ("model output was not a JSON object", "INVALID_JSON"),
    ("did not contain any requested ids", "ID_MAPPING_FAILURE"),
    ("did not return a translation for entry", "WRONG_OUTPUT_COUNT"),
    ("placeholder gone", "PLACEHOLDER_MISMATCH"),
    ("boom", "UNKNOWN_PROVIDER_ERROR"),
])
def test_failure_taxonomy(exc_msg, category):
    from almurrib.core.errors import ProviderError

    assert classify_failure(ProviderError(exc_msg)) == category


def test_health_panel_block():
    entries = [_entry(f"line {i}", i) for i in range(3)]
    stats = _run(entries, _ScriptedProvider(_arabic_mapping))
    health = health_snapshot(stats, provider=_ScriptedProvider(_arabic_mapping))
    lines = render_health(health)
    text = "\n".join(lines)
    assert "Progress: 3 / 3" in text and "Acceptance rate: 100.0%" in text
