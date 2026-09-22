"""Unity adapter tests.

Detection runs against the synthetic fixture (real structure + magic).
Walker/normalizer/write-back run against duck-typed fakes that mirror the
UnityPy surface used (documented in each fake) — real-binary parsing is
UnityPy's job and stays UNVERIFIED without a redistributable game.
"""

import sys
import types
from pathlib import Path

import pytest

from almurrib.core.errors import ExtractionError
from almurrib.core.model import EngineType
from almurrib.engine_adapters.unity import UnityAdapter
from almurrib.engine_adapters.unity import unityfs
from almurrib.engine_adapters.unity.unityfs import (
    UnityDependencyError,
    _apply_tree,
    _walk_strings,
    apply_translations,
    require_unitypy,
    sniff_version,
)


def _fixture():
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "unity_tiny"
    if not (fixture / "TinyGame_Data" / "globalgamemanagers").exists():
        pytest.skip("unity_tiny fixture not present")
    return fixture


def test_detect_synthetic_game():
    fixture = _fixture()
    result = UnityAdapter().detect(fixture)
    assert result.is_match
    assert result.engine is EngineType.UNITY
    assert any("UnityFS" in reason or "asset" in reason for reason in result.reasons)


def test_unity_detect_rejects_unrelated(tmp_path):
    assert not UnityAdapter().detect(tmp_path).is_match


def test_sniff_version_magic_only():
    fixture = _fixture()
    manager = fixture / "TinyGame_Data" / "globalgamemanagers"
    assert unityfs.UNITYFS_MAGIC == b"UnityFS"
    version = sniff_version(manager)
    assert version and "2022" in version
    assert sniff_version(manager.parent / "missing") is None


def test_all_candidates_unreadable_fails_loudly(monkeypatch):
    """An asset whose text objects all fail must explain, not return []."""

    class Boom:
        type = _FakeType("MonoBehaviour")
        path_id = 1

        def read_typetree(self):
            raise ValueError("old version without typetrees")

    class FakeUnityPy:
        @staticmethod
        def load(path):
            return types.SimpleNamespace(
                files={"f": _FakeFile([Boom()], {})})

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    with pytest.raises(ExtractionError) as exc_info:
        unityfs.iter_text_objects(Path("g.assets"))
    assert "typetree" in str(exc_info.value).lower()


def test_sheet_elements_split_and_classified():
    """EN sheets become source; other sheets are skipped; entities unescaped."""
    from almurrib.engine_adapters.unity.unityfs import (
        sheet_language,
        split_sheet_elements,
    )

    assert sheet_language("EN_Banker") == "en"
    assert sheet_language("BP_Banker") == "bp"
    assert sheet_language("plain") is None
    pairs = split_sheet_elements(
        '<entries><entry name="A">Hi &lt;page&gt; you</entry></entries>')
    assert pairs == [("A", "Hi <page> you")]
    assert split_sheet_elements("just prose") is None


def test_binary_blobs_skipped():
    from almurrib.engine_adapters.unity.unityfs import _is_binary_text

    assert _is_binary_text("ab\x00cd")
    assert _is_binary_text("\x01\x02\x03\x04")
    assert not _is_binary_text("مرحبا Hello 123!")


def test_sheet_end_to_end_in_adapter(tmp_path):
    """Sheet-shaped TextAssets extract per-key EN entries via the adapter."""
    game = tmp_path / "g"
    (game / "G_Data").mkdir(parents=True)

    import sys
    import types as _t

    blob_en = ("<entries><entry name=\"K1\">Hello.</entry>"
               "<entry name=\"K2\">Bye.</entry></entries>")
    blob_es = "<entries><entry name=\"K1\">Hola.</entry></entries>"

    class FakeUnityPy:
        @staticmethod
        def load(path):
            class T:
                def __init__(self, name, script):
                    self.m_Name = name
                    self.m_Script = script

            class O:
                def __init__(self, t):
                    self.type = _FakeType("TextAsset")
                    self.path_id = 1
                    self._t = t

                def read(self):
                    return self._t

            return _t.SimpleNamespace(files={
                "f": _FakeFile([O(T("EN_Sheet", blob_en)), O(T("ES_Sheet", blob_es))],
                               {1: ""})})

    import sys as _sys
    _sys.modules["UnityPy"] = FakeUnityPy
    try:
        (game / "G_Data" / "x.assets").write_bytes(b"stub")
        entries = UnityAdapter().extract(game)
    finally:
        del _sys.modules["UnityPy"]
    by_text = {e.source_text: e for e in entries}
    assert set(by_text) == {"Hello.", "Bye."}  # ES sheet skipped, not sourced
    assert by_text["Hello."].source_refs[0].statement == "sheet_entry"


def test_total_blackout_names_first_error(monkeypatch):
    """§25: when every object fails, the report names the cause."""

    class FailingObj:
        type = _FakeType("TextAsset")
        path_id = 1

        def read(self):
            raise FileNotFoundError("lzma.tpk missing in bundle")

    class FakeUnityPy:
        @staticmethod
        def load(path):
            return types.SimpleNamespace(
                files={"f": _FakeFile([FailingObj()], {1: ""})})

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    with pytest.raises(ExtractionError) as info:
        unityfs.iter_text_objects(Path("g.assets"))
    assert "FileNotFoundError: lzma.tpk missing in bundle" in str(info.value)


def test_malformed_asset_fails_clearly_not_crash(monkeypatch):
    """Garbage bytes are ExtractionError, never a raw traceback."""

    class FakeUnityPy:
        @staticmethod
        def load(path):
            raise RuntimeError("not a unity file at all")

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    from almurrib.core.errors import ExtractionError

    with pytest.raises(ExtractionError):
        unityfs.iter_text_objects(Path("g.assets"))


def test_missing_unitypy_gives_install_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "UnityPy", None)
    with pytest.raises(UnityDependencyError) as exc_info:
        require_unitypy()
    assert "unity" in str(exc_info.value).lower()
    assert isinstance(exc_info.value, ExtractionError)


# -- duck-typed UnityPy surface (mirrors the attributes used) -------------------

class _FakeType:
    def __init__(self, name):
        self.name = name


class _FakeTextAsset:
    def __init__(self, name, script):
        self.m_Name = name
        self.m_Script = script
        self.saved = False

    def save(self):
        self.saved = True


class _FakeMono:
    def __init__(self, tree):
        self._tree = tree
        self.saved = None

    def read_typetree(self):
        return self._tree

    def save_typetree(self, tree):
        self.saved = tree


class _FakeObj:
    def __init__(self, type_name, path_id, reader):
        self.type = _FakeType(type_name)
        self.path_id = path_id
        self._reader = reader

    def read(self):
        return self._reader

    def read_typetree(self):
        return self._reader.read_typetree()


class _FakeFile:
    def __init__(self, objects, container=None):
        self._objects = objects
        self.container = container or {}
        self.saved_bytes = None

    @property
    def objects(self):
        return self._objects

    def save(self):
        # Mirrors SerializedFile.save() -> bytes (verified signature).
        self.saved_bytes = b"REBUILT"
        return self.saved_bytes


def _fake_env(files):
    module = types.ModuleType("UnityPy")
    module.load = lambda path: types.SimpleNamespace(files=files)
    module.files = types.SimpleNamespace(
        SerializedFile=type("SerializedFile", (), {}))
    return module


def test_walk_strings_bounds_and_paths():
    tree = {"m_Name": "Herald", "greeting": "Hello traveler!",
            "nested": {"deep": ["a", "b"]}, "big": "x" * 5000, "n": 3}
    found = dict(_walk_strings(tree))
    assert found["greeting"] == "Hello traveler!"
    assert found["m_Name"] == "Herald"
    assert found["nested.deep[1]"] == "b"
    assert "big" not in found  # over-length blobs are data, not dialogue
    assert "n" not in found


def test_iter_text_objects_over_fakes(monkeypatch):
    calls = {}

    class FakeUnityPy:
        @staticmethod
        def load(path):
            calls["path"] = path
            text = _FakeTextAsset("Scroll", "Read me, {player_name}!")
            mono = _FakeObj("MonoBehaviour", 7, _FakeMono(
                {"m_Name": "Greeter", "line": "Welcome back!"}))
            text_obj = _FakeObj("TextAsset", 3, text)
            files = {"f": _FakeFile([text_obj, mono], {3: "Res", 7: "Res"})}
            return types.SimpleNamespace(files=files)

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    found = unityfs.iter_text_objects(Path("g.assets"))
    by_field = {(o.class_name, o.field_path): o.text for o in found}
    assert by_field[("TextAsset", "m_Script")] == "Read me, {player_name}!"
    assert by_field[("MonoBehaviour", "line")] == "Welcome back!"
    assert by_field[("MonoBehaviour", "m_Name")] == "Greeter"


def test_apply_tree_sets_only_mapped():
    tree = {"a": "old-a", "b": {"c": "old-c"}, "d": ["old-d"]}
    changed = _apply_tree(tree, "", {("", "a", "old-a"): "new-a",
                                     ("", "b.c", "WRONG"): "nope"})
    assert changed is True
    assert tree == {"a": "new-a", "b": {"c": "old-c"}, "d": ["old-d"]}


def test_write_back_round_trip_over_fakes(monkeypatch, tmp_path):
    from almurrib.core.model import LocalizationEntry, SourceRef
    from almurrib.engine_adapters.unity.reinject import write_asset_patch

    text = _FakeTextAsset("Scroll", "Read me!")
    holder = {}

    class FakeUnityPy:
        @staticmethod
        def load(path):
            obj = _FakeObj("TextAsset", 9, text)
            holder["file"] = _FakeFile([obj], {9: ""})
            return types.SimpleNamespace(files={"f": holder["file"]})

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    game = tmp_path / "game"
    (game / "TinyGame_Data").mkdir(parents=True)
    asset = game / "TinyGame_Data" / "test.assets"
    asset.write_bytes(b"stub")
    ref = SourceRef(file="TinyGame_Data/test.assets", line=1, statement="text_asset",
                    extra={"container": "", "field": "m_Script"})
    entry = LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.UNITY, "Read me!", ref),
        engine=EngineType.UNITY, source_text="Read me!",
        translated_text="اقرأني!", source_refs=[ref])
    out = tmp_path / "patch"
    written = write_asset_patch([entry], game_root=game, output_dir=out)
    assert written and (out / "TinyGame_Data" / "test.assets").exists()
    assert text.m_Script == "اقرأني!"
    assert asset.read_bytes() == b"stub"  # original untouched
