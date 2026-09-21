"""Overlay architecture tests (locale separation invariants)."""

from almurrib.core.overlay import Locales, OverlayPlan, OverlayStrategy
from almurrib.engine_adapters.renpy import RenPyAdapter


def test_plan_keeps_base_english():
    plan = OverlayPlan(engine="renpy", displayed_locale="ar",
                       strategy=OverlayStrategy.LANGUAGE_DIR)
    assert plan.base_locale == "en"
    assert plan.displayed_locale == "ar"
    assert plan.leaves_base_english


def test_renpy_adapter_declares_language_dir_strategy():
    plan = RenPyAdapter().overlay_plan(target_lang="ar")
    assert plan.strategy is OverlayStrategy.LANGUAGE_DIR
    assert plan.details["tl_dir"] == "game/tl/ar/"
    assert plan.leaves_base_english


def test_three_locales_never_conflated():
    locales = Locales(ui_locale="ar", game_base_locale="en",
                      displayed_locale="ar")
    assert locales.ui_locale != locales.game_base_locale
    assert locales.displayed_locale == "ar"
    assert locales.game_base_locale == "en"


def test_strategies_enumerated():
    assert {s.value for s in OverlayStrategy} == {
        "language_dir", "lookup_override", "resource_patch", "interception"}
