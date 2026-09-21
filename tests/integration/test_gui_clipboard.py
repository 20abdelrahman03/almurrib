"""Clipboard / editing regression tests for the GUI.

Headless-safe: uses a real Tk window when a display is available (always on
Windows desktop dev), skips otherwise. Verifies editable fields are editable,
the context menu attaches without crashing, clipboard copy/paste works via
the real system clipboard, and the masked API-key field stays masked on
screen while remaining copyable.
"""

import os

import pytest

pytest.importorskip("tkinter")


def _display() -> bool:
    return os.name == "nt" or bool(os.environ.get("DISPLAY"))


@pytest.fixture
def root():
    if not _display():
        pytest.skip("no display available")
    from tkinter import Tk

    root = Tk()
    root.withdraw()
    yield root
    root.destroy()


def _pump(root, times: int = 3) -> None:
    for _ in range(times):
        root.update_idletasks()
        root.update()


def test_fields_are_editable(root):
    from tkinter import Entry, StringVar

    from almurrib.gui.editing import attach_editing

    for label in ("game", "db", "src", "tgt", "provider", "url", "model", "key"):
        var = StringVar(value="x")
        entry = Entry(root, textvariable=var)
        attach_editing(entry)
        assert str(entry.cget("state")) == "normal"
        entry.insert("end", "y")
        assert var.get() == "xy"


def test_copy_paste_roundtrip_via_clipboard(root):
    from tkinter import Entry, StringVar

    from almurrib.gui.editing import _copy, _paste, _select_all, attach_editing

    var = StringVar(value="hello world")
    entry = Entry(root, textvariable=var)
    entry.pack()
    attach_editing(entry)

    _select_all(entry)
    _copy(entry)
    _pump(root)

    var2 = StringVar(value="")
    entry2 = Entry(root, textvariable=var2)
    entry2.pack()
    attach_editing(entry2)
    _paste(entry2)
    _pump(root)

    assert var2.get() == "hello world"


def test_masked_api_key_field_copyable_but_masked(root):
    from tkinter import Entry, StringVar

    from almurrib.gui.editing import _copy, _select_all

    var = StringVar(value="super-secret")
    entry = Entry(root, textvariable=var, show="*")
    entry.pack()
    # on screen the content is masked
    assert entry.cget("show") == "*"
    # but copy still yields the real value to the clipboard
    _select_all(entry)
    _copy(entry)
    _pump(root)
    assert root.clipboard_get() == "super-secret"


def test_context_menu_attaches_without_error(root):
    from tkinter import Entry, StringVar

    from almurrib.gui.editing import attach_editing

    entry = Entry(root, textvariable=StringVar(value="x"))
    entry.pack()
    attach_editing(entry)  # must not raise
    # right-click binding registered
    assert entry.bind("<Button-3>")


def test_ctrl_bindings_suppress_native_double_handling(root):
    """Ctrl+C/X/V/A must not run twice (ours + Tk's <<Copy>>/<<Paste>>/...).

    Without ``break`` a real keypress would e.g. paste twice and overwrite
    the clipboard with the masked ``***`` text on the API-key field.
    """
    from tkinter import Entry, StringVar

    from almurrib.gui.editing import attach_editing

    entry = Entry(root, textvariable=StringVar(value="x"))
    entry.pack()
    attach_editing(entry)
    for pattern in (
        "<Control-c>", "<Control-C>",
        "<Control-x>", "<Control-X>",
        "<Control-v>", "<Control-V>",
        "<Control-a>", "<Control-A>",
    ):
        assert "break" in (entry.bind(pattern) or ""), pattern


def test_no_ctrl_zw_breakage(root):
    """We bind no Ctrl+Z/Y handler, so native undo behaviour is untouched."""
    from tkinter import Entry, StringVar

    from almurrib.gui.editing import attach_editing

    entry = Entry(root, textvariable=StringVar(value="x"))
    entry.pack()
    attach_editing(entry)
    assert not entry.bind("<Control-z>")
    assert not entry.bind("<Control-Z>")
    assert not entry.bind("<Control-y>")
    assert not entry.bind("<Control-Y>")
