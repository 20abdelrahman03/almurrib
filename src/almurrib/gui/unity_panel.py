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

        btns = Frame(self.win)
        btns.pack(fill=X, padx=8, pady=4)
        self.btn_detect = Button(btns, text="Detect",
                                 command=self._on_detect)
        self.btn_detect.pack(side=LEFT, padx=4)
        self.btn_go = Button(btns, text="Localize Game",
                             command=self._on_localize,
                             font=("Segoe UI", 11, "bold"))
        self.btn_go.pack(side=LEFT, padx=4)
        self.btn_launch = Button(btns, text="Launch Game", state="disabled",
                                 command=self._on_launch)
        self.btn_launch.pack(side=LEFT, padx=4)

        Label(self.win, textvariable=self.info, anchor="w",
              wraplength=640, justify="left").pack(fill=X, padx=8, pady=4)
        self._workspace: Path | None = None
        self._worker: threading.Thread | None = None

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
        self.info.set(message)
        self._say(message)

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
                strategy=self.strategy.get())
            with Database(app._db()) as db:
                say = lambda m: self.win.after(0, self._say, m)
                report = localize_unity_game(
                    Path(self.game_dir.get()), db=db, provider=provider,
                    options=options,
                    progress=say, log=say)
            if report.workspace_root:
                self._workspace = Path(report.workspace_root)
                self.win.after(0, lambda: self.btn_launch.configure(
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
                       f"translated={report.translated} "
                       f"failed={report.failed} strategy={report.strategy}")
            if report.warnings:
                summary += " warnings: " + "; ".join(report.warnings)
            summary += " | " + report.support_note
            return summary

        self._run_async(work)

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
