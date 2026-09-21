"""Reusable text-editing helpers for Tkinter Entry widgets.

Tkinter's ``Entry`` already supports the native Windows clipboard for
Ctrl+C / Ctrl+V / Ctrl+X and full keyboard editing (Ctrl+A, arrows, Home,
End, Shift+selection, Ctrl+Z/Y on some builds). This module adds the one
thing Tkinter does *not* provide out of the box: a right-click context menu
(Cut / Copy / Paste / Select All), and makes sure clipboard shortcuts keep
working — including on the masked API-key field.

Design rules honoured here:
* The explicit Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+A bindings below *replace*
  Tk's matching virtual-event handling for that keypress (they return
  ``"break"``). This is required, not optional: without it, a real keypress
  would run our handler *and* Tk's native ``<<Copy>>`` / ``<<Cut>>`` /
  ``<<Paste>>`` / ``<<SelectAll>>`` class binding — pasting twice, and
  copying the masked ``***`` text instead of the real API key. Our handlers
  implement the exact same semantics on the real Windows clipboard, so
  nothing is lost. All other keys (Ctrl+Z/Y, Backspace, Delete, Home, End,
  arrows, Shift+selection, mouse selection) have no binding here and keep
  their native behaviour untouched.
* Clipboard operations use the real Windows clipboard (``clipboard_clear`` /
  ``clipboard_append`` / ``selection_get``), never a fake buffer.
* Nothing here logs clipboard contents or the API key.
"""

from __future__ import annotations

from tkinter import Entry, Menu, TclError


def _has_selection(entry: Entry) -> bool:
    try:
        return bool(entry.selection_present())
    except TclError:
        return False


def _entry_text(entry: Entry) -> str:
    """The real content of the field (textvariable first, so masked fields
    copy their real value, not the ``***`` shown on screen)."""
    var_name = str(entry.cget("textvariable"))
    if var_name:
        try:
            return entry.getvar(var_name)
        except TclError:
            pass
    return entry.get()


def _cut(entry: Entry) -> None:
    if _has_selection(entry) and str(entry.cget("state")) == "normal":
        _copy(entry)
        entry.delete("sel.first", "sel.last")


def _copy(entry: Entry) -> None:
    if not _has_selection(entry):
        return
    # selection_get() returns the masked text on show='*' widgets, so read
    # the real value from the textvariable and clip to the selection range.
    full = _entry_text(entry)
    first = entry.index("sel.first")
    last = entry.index("sel.last")
    text = full[first:last]
    entry.clipboard_clear()
    entry.clipboard_append(text)


def _paste(entry: Entry) -> None:
    if str(entry.cget("state")) != "normal":
        return
    try:
        text = entry.clipboard_get()
    except TclError:
        return  # empty clipboard
    if _has_selection(entry):
        entry.delete("sel.first", "sel.last")
    entry.insert("insert", text)


def _select_all(entry: Entry) -> None:
    entry.select_range(0, "end")
    entry.icursor("end")


def _on_copy(entry: Entry, _event=None) -> str:
    _copy(entry)
    return "break"  # handled: suppress the native <<Copy>> for this keypress


def _on_cut(entry: Entry, _event=None) -> str:
    _cut(entry)
    return "break"  # handled: suppress the native <<Cut>> for this keypress


def _on_paste(entry: Entry, _event=None) -> str:
    _paste(entry)
    return "break"  # handled: suppress the native <<Paste>> for this keypress


def _on_select_all(entry: Entry, _event=None) -> str:
    _select_all(entry)
    return "break"  # handled: suppress the native <<SelectAll>> for this keypress


def attach_editing(entry: Entry) -> None:
    """Attach a right-click context menu + explicit clipboard bindings.

    The explicit Ctrl+C/V/X/A bindings call the same clipboard logic as the
    context menu and return ``"break"`` so the matching native virtual-event
    binding does not run a second time for the same keypress. This keeps the
    masked API-key field copyable (Tk's native ``<<Copy>>`` reads the masked
    ``***`` text via ``selection_get``; ours reads the real value from the
    textvariable, which is what lets the user paste their key back out of
    the app). Every other key keeps its native behaviour.
    """
    menu = Menu(entry, tearoff=0)
    menu.add_command(label="Cut", command=lambda: _cut(entry))
    menu.add_command(label="Copy", command=lambda: _copy(entry))
    menu.add_command(label="Paste", command=lambda: _paste(entry))
    menu.add_separator()
    menu.add_command(label="Select All", command=lambda: _select_all(entry))

    def popup(event) -> None:
        entry.focus_set()
        menu.tk_popup(event.x_root, event.y_root)

    entry.bind("<Button-3>", popup)

    # Explicit clipboard bindings (handled here, native suppressed per keypress).
    entry.bind("<Control-c>", lambda e: _on_copy(entry, e))
    entry.bind("<Control-C>", lambda e: _on_copy(entry, e))
    entry.bind("<Control-x>", lambda e: _on_cut(entry, e))
    entry.bind("<Control-X>", lambda e: _on_cut(entry, e))
    entry.bind("<Control-v>", lambda e: _on_paste(entry, e))
    entry.bind("<Control-V>", lambda e: _on_paste(entry, e))
    entry.bind("<Control-a>", lambda e: _on_select_all(entry, e))
    entry.bind("<Control-A>", lambda e: _on_select_all(entry, e))
