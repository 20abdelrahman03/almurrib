"""Unity one-click panel (§24 of the milestone).

A separate ``Toplevel`` opened from the main window ("Unity…" button).
It reuses the main app's provider/database/language settings and calls
the SHARED :func:`localize_unity_game` service on a background thread —
the same service the ``almurrib unity localize`` CLI uses. No workflow
logic is duplicated here.

Layout mirrors the prompt's one-click sketch: game folder, detected
profile + capabilities, strategy, [ Localize Game ], progress readout,
[ Launch Game ] when a workspace is ready.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path


class UnityPanel:
    """Unity one-click window bound to a live ``AlmurribApp`` instance."""

    def __init__(self, app) -> None:
        from tkinter import (BOTH, END, LEFT, RIGHT, WORD, Button, Entry,
                             Frame, Label, LabelFrame, StringVar, Text,
                             Toplevel, X, filedialog)

        self._app = app
        self._filedialog = filedialog
        self.game_dir = StringVar(value=app.game_dir.get())
        self.strategy = StringVar(value="auto")
        self.info = StringVar(value="")

        self.win = Toplevel(app.root)
        self.win.title("Almurrib — Unity one-click")
        self.win.geometry("680x560")

        top = Frame(self.win)
        top.pack(fill=X, padx=8, pady=6)
        Label(top, text="Game Folder:", width=12, anchor="w").pack(side=LEFT)
        Entry(top, textvariable=self.game_dir).pack(side=LEFT, fill=X,
                                                   expand=True)
        Button(top, text="Browse…", command=self._browse).pack(side=RIGHT)

        det = LabelFrame(self.win, text="Detected")
        det.pack(fill=BOTH, expand=True, padx=8, pady=4)
        self.text = Text(det, height=16, wrap=WORD)
        self.text.pack(fill=BOTH, expand=True)

        row = Frame(self.win)
        row.pack(fill=X, padx=8, pady=4)
        Label(row, text="Strategy:", anchor="w").pack(side=LEFT)
        for value in ("auto", "static", "runtime"):
            from tkinter import Radiobutton

            Radiobutton(row, text=value, variable=self.strategy,
                        value=value).pack(side=LEFT)

        row_font = Frame(self.win)
        row_font.pack(fill=X, padx=8, pady=2)
        from tkinter import BooleanVar, Checkbutton

        self.visual_arabic = BooleanVar(value=True)
        Checkbutton(row_font, text="Visual Arabic order (legacy Unity fonts)",
                    variable=self.visual_arabic, anchor="w").pack(side=LEFT)

        btns = Frame(self.win)
        btns.pack(fill=X, padx=8, pady=4)
        self.btn_detect = Button(btns, text="Detect",
                                 command=self._on_detect)
        self.btn_detect.pack(side=LEFT, padx=4)
        self.btn_go = Button(btns, text="Localize Game",
                             command=self._on_localize,
                             font=("Segoe UI", 11, "bold"))
        self.btn_go.pack(side=LEFT, padx=4)
        self.btn_stop = Button(btns, text="Stop", state="disabled",
                               command=self._on_stop)
        self.btn_stop.pack(side=LEFT, padx=4)
        self.btn_pause = Button(btns, text="Pause", state="disabled",
                                command=self._on_pause)
        self.btn_pause.pack(side=LEFT, padx=4)
        self.btn_launch = Button(btns, text="Launch Game", state="disabled",
                                 command=self._on_launch)
        self.btn_launch.pack(side=LEFT, padx=4)

        btns2 = Frame(self.win)
        btns2.pack(fill=X, padx=8, pady=2)
        self.btn_explain = Button(btns2, text="Explain text…",
                                  command=self._on_explain)
        self.btn_explain.pack(side=LEFT, padx=4)
        self.btn_rollback = Button(btns2, text="Restore workspace",
                                   state="disabled",
                                   command=self._on_rollback)
        self.btn_rollback.pack(side=LEFT, padx=4)

        Label(self.win, textvariable=self.info, anchor="w",
              wraplength=640, justify="left").pack(fill=X, padx=8, pady=4)
        self._workspace: Path | None = None
        self._worker: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._paused = False

    # ----- widgets --------------------------------------------------------

    def _browse(self) -> None:
        picked = self._filedialog.askdirectory(title="Choose Unity game folder")
        if picked:
            self.game_dir.set(picked)

    def _say(self, message: str) -> None:
        self.text.configure(state="normal")
        self.text.insert(END, message + "\n")
        self.text.configure(state="disabled")
        self.text.see(END)

    def _run_async(self, work) -> None:
        if self._worker and self._worker.is_alive():
            self.info.set("An operation is already running.")
            return
        self.btn_go.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_pause.configure(state="normal")
        self.btn_explain.configure(state="disabled")
        self.btn_rollback.configure(state="disabled")
        self._stop_event.clear()
        self._pause_event.clear()
        self._paused = False
        self.btn_pause.configure(text="Pause")

        def runner() -> None:
            try:
                message = work()
                self.win.after(0, lambda: self._done(True, message))
            except Exception as exc:  # never crash the UI thread
                self.win.after(0, lambda: self._done(False, str(exc)))

        self._worker = threading.Thread(target=runner, daemon=True)
        self._worker.start()

    def _done(self, ok: bool, message: str) -> None:
        self.btn_go.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_pause.configure(state="disabled")
        self.btn_explain.configure(state="normal")
        if self._workspace is not None:
            self.btn_rollback.configure(state="normal")
        self._stop_event.clear()
        self._pause_event.clear()
        self.info.set(message)
        self._say(message)

    def _on_stop(self) -> None:
        self._stop_event.set()
        self.info.set("stopping after the current batch... "
                      "(accepted work is already saved)")

    def _on_pause(self) -> None:
        if self._paused:
            self._pause_event.clear()
            self._paused = False
            self.btn_pause.configure(text="Pause")
            self.info.set("resumed.")
        else:
            self._pause_event.set()
            self._paused = True
            self.btn_pause.configure(text="Resume")
            self.info.set("pausing after the current batch...")

    # ----- actions --------------------------------------------------------

    def _on_detect(self) -> None:
        # Structured analysis is stdlib-only and fast: run inline, no thread.
        from tkinter import END as _END

        from almurrib.engine_adapters.unity import analysis as A

        profile = A.analyze_game(Path(self.game_dir.get()))
        self.text.configure(state="normal")
        self.text.delete("1.0", _END)
        self._say(f"Unity: {profile.unity_version or 'unknown'} / "
                  f"{profile.backend.value} / {profile.arch or '?'}")
        self._say(f"Assets: {profile.serialized_assets}, "
                  f"bundles: {len(profile.bundles)}")
        for line in A.capability_summary(profile):
            self._say(line)
        self.info.set("detection complete")

    def _on_localize(self) -> None:
        def work() -> str:
            from almurrib.engine_adapters.unity.service import (
                UnityLocalizeOptions,
                localize_unity_game,
            )
            from almurrib.storage.database import Database

            app = self._app
            provider = app._provider()
            options = UnityLocalizeOptions(
                target_lang=app._target_code(),
                source_lang=app._source_code(),
                strategy=self.strategy.get(),
                visual_arabic=bool(self.visual_arabic.get()))
            with Database(app._db()) as db:
                say = lambda m: self.win.after(0, self._say, m)
                report = localize_unity_game(
                    Path(self.game_dir.get()), db=db, provider=provider,
                    options=options,
                    progress=say, log=say,
                    stop_event=self._stop_event,
                    pause_event=self._pause_event)
            if report.workspace_root:
                self._workspace = Path(report.workspace_root)
                self.win.after(0, lambda: self.btn_launch.configure(
                    state="normal"))
                self.win.after(0, lambda: self.btn_rollback.configure(
                    state="normal"))
            from almurrib.core.translate import (
                TranslationHealth,
                render_health,
            )

            for line in render_health(TranslationHealth(
                    provider=provider.config.provider,
                    model=provider.config.model,
                    total=report.extracted, accepted=report.translated,
                    failed=report.failed)):
                self.win.after(0, self._say, line)
            summary = (f"extracted={report.extracted} "
                       f"unique={report.unique} cached={report.cached} "
                       f"translated={report.translated} "
                       f"accepted={report.accepted} "
                       f"failed={report.failed} strategy={report.strategy}")
            if report.warnings:
                summary += " warnings: " + "; ".join(report.warnings)
            summary += " | " + report.support_note
            return summary

        self._run_async(work)

    def _on_explain(self) -> None:
        # Per-entry diagnostics (§21): "why isn't this text translated?"
        from tkinter import simpledialog

        needle = simpledialog.askstring(
            "Explain text", "Source text to look up:",
            parent=self.win)
        if not needle:
            return
        from almurrib.core.workflow import resolve_project
        from almurrib.engine_adapters.unity.service import explain_entry
        from almurrib.storage.database import Database
        from almurrib.storage.repository import EntryRepository

        with Database(self._app._db()) as db:
            project = resolve_project(db, Path(self.game_dir.get()))
            entries = EntryRepository(db).list(
                project_id=project.id if project else None)
        shown = 0
        for entry in entries:
            if needle.lower() not in entry.source_text.lower():
                continue
            report = explain_entry(entry)
            self._say(f"--- {report['location']}")
            for key in ("source", "asset_class", "field",
                        "extraction_method", "candidate_class",
                        "translation", "qa_flags", "write_back", "fallback"):
                self._say(f"  {key}: {report[key]}")
            shown += 1
            if shown >= 5:
                break
        if not shown:
            self.info.set("no stored entries contain that text")

    def _on_rollback(self) -> None:
        if not self._workspace:
            return
        from tkinter import messagebox

        if not messagebox.askyesno(
                "Restore workspace",
                "Remove the localized working copy? The original game was "
                "never modified; this only deletes the copy."):
            return
        from almurrib.engine_adapters.unity.workspace import rollback_workspace

        try:
            problems = rollback_workspace(self._workspace)
        except Exception as exc:
            self.info.set(f"rollback failed: {exc}")
            return
        self._workspace = None
        self.btn_launch.configure(state="disabled")
        self.btn_rollback.configure(state="disabled")
        if problems:
            self.info.set("copy removed, BUT sources looked different — "
                          "investigate before trusting.")
        else:
            self.info.set("workspace removed; original game verified untouched.")

    def _on_launch(self) -> None:
        if not self._workspace:
            return
        exes = sorted(self._workspace.glob("*.exe"))
        if not exes:
            self.info.set("no game exe in workspace root")
            return
        try:
            subprocess.Popen([str(exes[0])], cwd=str(self._workspace),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            self.info.set(f"launched {exes[0].name}")
        except OSError as exc:
            self.info.set(f"cannot launch ({exc})")


def open_unity_panel(app) -> None:
    """Entry point wired to the main window's Unity button."""
    UnityPanel(app)
