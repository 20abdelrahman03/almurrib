"""Minimal Tkinter GUI for Almurrib.

This is a *frontend only*: every button delegates to the existing
``almurrib.core.workflow`` / ``almurrib.core.config`` / ``almurrib.providers``
services. No extraction/translation logic lives here.

Threading model: long operations run on a daemon background thread and post
results back to the Tk main loop through a ``queue.Queue``; the UI polls the
queue with ``after()`` so the window never blocks. The API key is masked in
the UI and never written to the log.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from tkinter import (
    BOTH, END, LEFT, RIGHT, X,
    Button, Entry, Frame, Label, LabelFrame, StringVar, Text, Tk,
    filedialog, messagebox,
)
from tkinter.ttk import Progressbar

from almurrib.core.config import ENV_PREFIX, load_settings, save_env_file
from almurrib.core.errors import AlMurribError
from almurrib.core.pipeline import LocalizationPipeline
from almurrib.core.workflow import (
    export_translations,
    extract_and_store,
    translate_entries,
)
from almurrib.engine_adapters import default_adapters
from almurrib.providers import build_provider
from almurrib.storage.database import Database
from almurrib.storage.repository import EntryRepository

WINDOW_TITLE = "المعرب — Almurrib"


class AlmurribApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title(WINDOW_TITLE)
        root.geometry("720x640")

        self._queue: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None

        self._settings = load_settings()

        self.game_dir = StringVar(value="")
        self.db_path = StringVar(value=str(self._settings.database_path))
        self.source_lang = StringVar(value=self._settings.source_lang)
        self.target_lang = StringVar(value=self._settings.target_lang)
        self.provider = StringVar(value=self._settings.provider)
        self.base_url = StringVar(value=self._settings.base_url)
        self.model = StringVar(value=self._settings.model)
        self.api_key = StringVar(value=self._settings.api_key or "")

        self._build_ui()
        self.root.after(80, self._poll_queue)

    # ------------------------------------------------------------- UI layout

    def _build_ui(self) -> None:
        pad = {"padx": 6, "pady": 3}

        frm_game = Frame(self.root)
        frm_game.pack(fill=X, **pad)
        Label(frm_game, text="Game Folder:", width=14, anchor="w").pack(side=LEFT)
        Entry(frm_game, textvariable=self.game_dir).pack(side=LEFT, fill=X, expand=True)
        Button(frm_game, text="اختيار مجلد اللعبة", command=self._pick_game).pack(side=RIGHT)

        frm_db = Frame(self.root)
        frm_db.pack(fill=X, **pad)
        Label(frm_db, text="Database:", width=14, anchor="w").pack(side=LEFT)
        Entry(frm_db, textvariable=self.db_path).pack(side=LEFT, fill=X, expand=True)
        Button(frm_db, text="Browse…", command=self._pick_db).pack(side=RIGHT)

        frm_lang = Frame(self.root)
        frm_lang.pack(fill=X, **pad)
        Label(frm_lang, text="Source:").pack(side=LEFT)
        Entry(frm_lang, textvariable=self.source_lang, width=10).pack(side=LEFT, padx=(2, 16))
        Label(frm_lang, text="Target:").pack(side=LEFT)
        Entry(frm_lang, textvariable=self.target_lang, width=10).pack(side=LEFT, padx=(2, 0))

        frm_prov = LabelFrame(self.root, text="Provider Configuration")
        frm_prov.pack(fill=X, **pad)
        self._labeled_entry(frm_prov, "Provider:", self.provider, 0)
        self._labeled_entry(frm_prov, "Base URL:", self.base_url, 1)
        self._labeled_entry(frm_prov, "Model:", self.model, 2)
        key_entry = self._labeled_entry(frm_prov, "API Key:", self.api_key, 3)
        key_entry.config(show="*")  # mask the API key
        Button(frm_prov, text="Save Configuration", command=self._save_config).grid(
            row=4, column=1, sticky="e", padx=4, pady=4
        )

        frm_actions = Frame(self.root)
        frm_actions.pack(fill=X, **pad)
        self.btn_detect = Button(frm_actions, text="Detect", command=self._on_detect)
        self.btn_extract = Button(frm_actions, text="Extract", command=self._on_extract)
        self.btn_translate = Button(frm_actions, text="Translate", command=self._on_translate)
        self.btn_export = Button(frm_actions, text="Export", command=self._on_export)
        for b in (self.btn_detect, self.btn_extract, self.btn_translate, self.btn_export):
            b.pack(side=LEFT, padx=3, expand=True, fill=X)

        self.btn_localize = Button(
            self.root, text="LOCALIZE GAME", command=self._on_localize,
            font=("Segoe UI", 11, "bold"),
        )
        self.btn_localize.pack(fill=X, padx=6, pady=6)
        self._action_buttons = [
            self.btn_detect, self.btn_extract, self.btn_translate,
            self.btn_export, self.btn_localize,
        ]

        self.progress = Progressbar(self.root, mode="determinate", maximum=100)
        self.progress.pack(fill=X, padx=6, pady=3)

        frm_log = LabelFrame(self.root, text="Log")
        frm_log.pack(fill=BOTH, expand=True, padx=6, pady=6)
        self.log = Text(frm_log, state="disabled", wrap="word", height=12)
        self.log.pack(fill=BOTH, expand=True)

    @staticmethod
    def _labeled_entry(parent, label, variable, row) -> Entry:
        Label(parent, text=label, width=12, anchor="w").grid(row=row, column=0, sticky="w", padx=4)
        entry = Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
        parent.columnconfigure(1, weight=1)
        return entry

    # ------------------------------------------------------------- logging

    def _log(self, level: str, message: str) -> None:
        # Never log secrets.
        key = self.api_key.get()
        if key:
            message = message.replace(key, "***")
        self.log.configure(state="normal")
        self.log.insert(END, f"[{level}] {message}\n")
        self.log.see(END)
        self.log.configure(state="disabled")

    def _info(self, message: str) -> None:
        self._log("INFO", message)

    def _ok(self, message: str) -> None:
        self._log("OK", message)

    def _error(self, message: str) -> None:
        self._log("ERROR", message)

    # ------------------------------------------------------------- pickers

    def _pick_game(self) -> None:
        path = filedialog.askdirectory(title="اختيار مجلد اللعبة")
        if path:
            self.game_dir.set(path)

    def _pick_db(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Database", defaultextension=".db",
            filetypes=[("SQLite", "*.db"), ("All", "*.*")],
        )
        if path:
            self.db_path.set(path)

    # ------------------------------------------------------------- config

    def _save_config(self) -> None:
        env_path = Path(".env")
        try:
            save_env_file(env_path, {
                ENV_PREFIX + "PROVIDER": self.provider.get(),
                ENV_PREFIX + "BASE_URL": self.base_url.get(),
                ENV_PREFIX + "MODEL": self.model.get(),
                ENV_PREFIX + "API_KEY": self.api_key.get(),
                ENV_PREFIX + "SOURCE_LANG": self.source_lang.get(),
                ENV_PREFIX + "TARGET_LANG": self.target_lang.get(),
                ENV_PREFIX + "DATABASE": self.db_path.get(),
            })
        except OSError as exc:
            self._error(f"could not save configuration: {exc}")
            return
        self._settings = load_settings(env_file=env_path)
        self._ok(f"configuration saved to {env_path}")

    # ------------------------------------------------------------- helpers

    def _game_path(self) -> Path:
        return Path(self.game_dir.get().strip() or ".")

    def _db(self) -> Path:
        return Path(self.db_path.get().strip() or "almurrib.db")

    def _provider(self):
        # Build a fresh provider from the on-screen fields (not stale settings).
        from almurrib.core.provider import ProviderConfig

        config = ProviderConfig(
            provider=self.provider.get().strip() or "openai_compat",
            model=self.model.get().strip(),
            base_url=self.base_url.get().strip(),
            api_key=self.api_key.get().strip(),
        )
        return build_provider(config)

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        for button in self._action_buttons:
            button.config(state=state)

    def _run_async(self, label: str, work, determinate: bool = False) -> None:
        """Run ``work()`` on a background thread; ``work`` returns a message."""
        if self._worker and self._worker.is_alive():
            messagebox.showinfo(WINDOW_TITLE, "An operation is already running.")
            return
        self._set_running(True)
        self._info(label)
        if not determinate:
            self.progress.config(mode="indeterminate")
            self.progress.start(12)
        else:
            self.progress.config(mode="determinate", maximum=100, value=0)

        def runner() -> None:
            try:
                message = work()
                self._queue.put(("ok", message))
            except AlMurribError as exc:
                self._queue.put(("error", str(exc)))
            except Exception as exc:  # defensive: never crash the UI thread
                self._queue.put(("error", f"unexpected error: {exc}"))

        self._worker = threading.Thread(target=runner, daemon=True)
        self._worker.start()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "ok":
                    self.progress.stop()
                    self.progress.config(mode="determinate", value=100)
                    self._set_running(False)
                    self._ok(payload)
                elif kind == "error":
                    self.progress.stop()
                    self.progress.config(mode="determinate", value=0)
                    self._set_running(False)
                    self._error(payload)
                    messagebox.showerror(WINDOW_TITLE, payload)
                elif kind == "progress":
                    done, total = payload
                    self.progress.config(mode="determinate", maximum=max(total, 1), value=done)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    def _progress_cb(self, done: int, total: int) -> None:
        self._queue.put(("progress", (done, total)))

    # ------------------------------------------------------------- actions

    def _on_detect(self) -> None:
        def work() -> str:
            pipeline = LocalizationPipeline(adapters=default_adapters())
            adapter = pipeline.detect_engine(self._game_path())
            result = adapter.detect(self._game_path())
            return f"{result.engine.value} detected (confidence {result.confidence:.2f})"

        self._run_async("Detecting engine...", work)

    def _on_extract(self) -> None:
        def work() -> str:
            pipeline = LocalizationPipeline(adapters=default_adapters())
            with Database(self._db()) as db:
                entries, _ = extract_and_store(
                    pipeline, self._game_path(), db, target_lang=self.target_lang.get()
                )
            return f"{len(entries)} entries extracted"

        self._run_async("Extracting text...", work)

    def _on_translate(self) -> None:
        def work() -> str:
            provider = self._provider()
            with Database(self._db()) as db:
                repo = EntryRepository(db)
                entries = repo.list()
                if not entries:
                    return "no entries stored — run Extract first"
                stats = translate_entries(
                    entries, db, provider,
                    source_lang=self.source_lang.get(),
                    target_lang=self.target_lang.get(),
                    progress=self._progress_cb,
                )
                repo.upsert_for_entries(entries)
            return (
                f"{stats.api_translated + stats.cache_hits + stats.memory_hits}"
                f"/{stats.total} translated "
                f"(api={stats.api_translated}, cache={stats.cache_hits}, "
                f"memory={stats.memory_hits}, failed={stats.failed})"
            )

        self._run_async("Translating...", work, determinate=True)

    def _on_export(self) -> None:
        def work() -> str:
            pipeline = LocalizationPipeline(adapters=default_adapters())
            with Database(self._db()) as db:
                written = export_translations(
                    pipeline, self._game_path(), db,
                    output_dir=Path(self._settings.output_dir),
                    target_lang=self.target_lang.get(),
                )
            files = "; ".join(str(p) for p in written)
            return f"exported {len(written)} file(s): {files}"

        self._run_async("Exporting localization...", work)

    def _on_localize(self) -> None:
        def work() -> str:
            pipeline = LocalizationPipeline(adapters=default_adapters())
            provider = self._provider()
            with Database(self._db()) as db:
                entries, project_id = extract_and_store(
                    pipeline, self._game_path(), db, target_lang=self.target_lang.get()
                )
                stats = translate_entries(
                    entries, db, provider,
                    source_lang=self.source_lang.get(),
                    target_lang=self.target_lang.get(),
                    project_id=project_id,
                    progress=self._progress_cb,
                )
                written = export_translations(
                    pipeline, self._game_path(), db,
                    output_dir=Path(self._settings.output_dir),
                    target_lang=self.target_lang.get(),
                )
            return (
                f"{len(entries)} extracted; {stats.api_translated} translated via API; "
                f"{len(written)} file(s) exported to {self._settings.output_dir}"
            )

        self._run_async("Running full localization...", work, determinate=True)


def main() -> None:
    """Launch the Almurrib GUI."""
    root = Tk()
    AlmurribApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
