"""Phase C/D tests: workspace safety, tool registry, XUnity interop."""

import json
import random

from almurrib.core.model import EngineType, EntryStatus, LocalizationEntry, SourceRef
from almurrib.engine_adapters.unity import runtime as R
from almurrib.engine_adapters.unity import tools as T
from almurrib.engine_adapters.unity import workspace as W


# ----- workspace --------------------------------------------------------


def _game(root, *, name="G", manager="globalgamemanagers"):
    game = root / name
    data = game / f"{name}_Data"
    data.mkdir(parents=True)
    (data / manager).write_bytes(b"UnityFS" + b"\x00" * 32)
    (data / "a.assets").write_bytes(b"asset-bytes")
    return game


def test_workspace_copy_verify_discard(tmp_path):
    game = _game(tmp_path)
    ws = W.prepare_workspace(game, tmp_path / "work")
    assert ws.game_id and ws.manifest_path.is_file()
    manifest = json.loads(ws.manifest_path.read_text(encoding="utf-8"))
    assert manifest["game_id"] == ws.game_id
    assert W.verify_originals(ws) == []
    # Touch the SOURCE -> verification must catch it.
    (game / "G_Data" / "a.assets").write_bytes(b"tampered")
    assert W.verify_originals(ws) != []
    W.discard(ws)
    assert not ws.root.exists() and game.is_dir()  # original survives


def test_workspace_refuses_existing_dest(tmp_path):
    game = _game(tmp_path)
    (tmp_path / "work").mkdir()
    try:
        W.prepare_workspace(game, tmp_path / "work")
    except Exception as exc:
        assert "exists" in str(exc)
    else:
        raise AssertionError("should refuse existing destination")


def test_game_identity_stable_across_moves(tmp_path):
    game = _game(tmp_path)
    first = W.game_identity(game)
    moved = tmp_path / "Elsewhere"
    game.rename(moved)
    assert W.game_identity(moved) == first


# ----- tools ------------------------------------------------------------


def test_registry_has_researched_versions():
    by_key = {t.key: t for t in T.REGISTRY}
    assert by_key["uabea"].version == "v8"
    assert by_key["bepinex"].version.startswith("5.4.23.5")
    assert by_key["xunity"].version == "5.6.2"
    assert "LGPL" in by_key["bepinex"].license
    assert all(t.method in ("dependency", "external", "reference")
               for t in T.REGISTRY)


def test_probe_bepinex_xunity_in_game_dir(tmp_path):
    assert not T.probe("bepinex", tmp_path).installed
    (tmp_path / "BepInEx" / "plugins" / "XUnity.AutoTranslator").mkdir(
        parents=True)
    assert T.probe("bepinex", tmp_path).installed
    assert T.probe("xunity", tmp_path).installed
    assert "unknown" in T.probe("nope").detail


# ----- XUnity interop ---------------------------------------------------

def _xunity_decode_line(line: str):
    """Faithful port of XUnity TextHelper.ReadTranslationLineAndDecode.

    Used ONLY to prove our encoder output parses back per XUnity's own
    rules (no XUnity code in this repo).
    """
    if not line:
        return None
    parts, current, escape_next, idx = ["", ""], [], False, 0
    text = list(line)
    buf: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if escape_next:
            if char in ("=", "\\"):
                buf.append(char)
            elif char == "n":
                buf.append("\n")
            elif char == "r":
                buf.append("\r")
            elif char == "u":
                code = text[i + 1:i + 5]
                if len(code) < 4:
                    raise ValueError("bad unicode escape")
                buf.append(chr(int("".join(code), 16)))
                i += 4
            else:
                buf.append("\\")
                buf.append(char)
            escape_next = False
        elif char == "\\":
            escape_next = True
        elif char == "=":
            if idx > 1:
                return None
            parts[idx] = "".join(buf)
            idx += 1
            buf = []
        elif char == "%" and text[i + 1:i + 3] == ["3", "D"]:
            buf.append("=")
            i += 2
        elif char == "/" and i + 1 < len(text) and text[i + 1] == "/":
            parts[idx] = "".join(buf)
            idx += 1
            return parts if idx == 2 else None
        else:
            buf.append(char)
        i += 1
    if idx != 1:
        return None
    parts[1] = "".join(buf)
    return parts


def test_encoder_round_trips_through_xunity_rules():
    nasty = ["a=b", "back\\slash", "line\nbreak", "double//slash",
             "percent%3Dseq", "tab\there", "مرحبا=عالم\\ test",
             "trailing\\", "=lead", "a//b=c", "quote\"q", "semi;semi"]
    rng = random.Random(42)
    alphabet = list("ab=\\/\n%مرحبا ") + nasty
    cases = list(nasty)
    for _ in range(200):
        cases.append("".join(rng.choice(alphabet) for _ in range(rng.randint(0, 24))))
    for original in cases:
        for side in (original, "ترجمة " + original):
            encoded = R.xunity_encode(side)
            decoded = _xunity_decode_line(f"KEY={encoded}")
            assert decoded is not None, encoded
            expected = side
            if "//" in expected:
                # Upstream XUnity quirk #1 (verified in TextHelper.cs):
                # `//` encodes to `\/` + `\/` but decodes back to itself,
                # so `//` texts can never match at runtime.
                expected = expected.replace("//", "\\/\\/")
            if "%3D" in expected:
                # Upstream quirk #2: the decoder maps legacy `%3D` to `=`,
                # so a literal `%3D` in game text never matches either.
                expected = expected.replace("%3D", "=")
            # In both cases we mirror the plugin byte-for-byte (including
            # its quirks) instead of inventing our own escaping.
            assert decoded[1] == expected, (side, encoded, decoded)


def _entry(source, translated, status=EntryStatus.TRANSLATED):
    ref = SourceRef(file="g/a.assets", line=1, statement="sheet_entry")
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.UNITY, source, ref),
        engine=EngineType.UNITY, source_text=source,
        translated_text=translated, status=status, source_refs=[ref])


def test_bundle_generation_filters_and_reports(tmp_path):
    entries = [
        _entry("Hello.", "مرحبا."),
        _entry("Hello.", "مرحبا!"),          # duplicate source
        _entry("x" * 3000, "y" * 3000),      # too long for XUnity
        _entry("Gone", None, EntryStatus.UNTRANSLATED),
    ]
    bundle = R.generate_xunity_bundle(entries, tmp_path / "bundle")
    assert bundle.pairs == 1
    assert bundle.skipped_long == 1
    assert bundle.skipped_empty == 1
    assert bundle.duplicate_sources == 1
    text = (tmp_path / "bundle" / "Translation" / "ar" / "Text"
            / "Almurrib_ar.txt").read_text(encoding="utf-8")
    assert text == "Hello.=مرحبا!\n"  # last duplicate wins, encoded
    config = (tmp_path / "bundle" / "Config.ini").read_text(encoding="utf-8")
    assert "Endpoint=" in config and "Language=ar" in config
