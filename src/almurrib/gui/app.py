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
    BooleanVar, Button, Entry, Frame, Label, LabelFrame, Menu, StringVar,
    Text, Tk, TclError, filedialog, messagebox,
)
from tkinter.ttk import Combobox, Progressbar

from almurrib.core.config import (
    ENV_PREFIX,
    default_env_file,
    load_settings,
    save_env_file,
)
from almurrib.core.errors import AlMurribError, AuthenticationError
from almurrib.core.paths import app_base_dir
from almurrib.core.pipeline import LocalizationPipeline
from almurrib.core.workflow import (
    export_translations,
    extract_and_store,
    resolve_project,
    translate_entries,
)
from almurrib.engine_adapters import default_adapters
from almurrib.gui.editing import attach_editing
from almurrib.providers import build_provider, get_definition, list_definitions
from almurrib.providers.discovery import ModelInfo, fetch_models
from almurrib.storage.database import Database
from almurrib.storage.repository import EntryRepository

WINDOW_TITLE = "المعرب — Almurrib"

# Shared formatter (lives in Core so the CLI uses the exact same wording).
from almurrib.core.reporting import (
    format_translation_error,
    provider_display_name,
)


# Display label -> language code (target doubles as the tl/<lang> dir name,
# so only safe identifiers appear here; validated again at export).
SOURCE_LANGS = {
    "English": "en",
    "Arabic": "ar",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Japanese": "ja",
}
TARGET_LANGS = {
    "Arabic (ar)": "ar",
    "Arabic (arabic)": "arabic",
    "English (en)": "en",
    "French (fr)": "fr",
    "German (de)": "de",
    "Spanish (es)": "es",
    "Japanese (ja)": "ja",
}


def _label_for(mapping: dict[str, str], code: str, default: str) -> str:
    for label, value in mapping.items():
        if value == code:
            return label
    return default


def _anchored(path, base: Path) -> Path:
    """Resolve a configured path against the app base dir (EXE stability).

    Absolute paths pass through untouched; relative defaults (``almurrib.db``,
    ``out``) anchor next to the executable when frozen, else to the CWD.
    """
    from pathlib import Path as _Path

    candidate = _Path(path)
    return candidate if candidate.is_absolute() else base / candidate


def _provider_display(provider_id: str) -> str:
    definition = get_definition(provider_id)
    return definition.display_name if definition else provider_id


class AlmurribApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title(WINDOW_TITLE)
        root.geometry("760x720")

        self._queue: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._models: list[ModelInfo] = []  # last fetched catalog
        self._model_pool: list[str] = []  # ids behind the dropdown (live/fallback)

        self._settings = load_settings()
        base = app_base_dir()

        self.game_dir = StringVar(value="")
        self.db_path = StringVar(value=str(_anchored(self._settings.database_path, base)))
        self.output_dir = StringVar(value=str(_anchored(self._settings.output_dir, base)))
        self.source_lang = StringVar(
            value=_label_for(SOURCE_LANGS, self._settings.source_lang, "English")
        )
        self.target_lang = StringVar(
            value=_label_for(TARGET_LANGS, self._settings.target_lang, "Arabic (ar)")
        )
        self.provider_name = StringVar(value=_provider_display(self._settings.provider))
        self.base_url = StringVar(value=self._settings.base_url)
        self.model = StringVar(value=self._settings.model)
        self.api_key = StringVar(value=self._settings.api_key or "")
        self.force = BooleanVar(value=False)

        self._build_ui()
        self._on_provider_changed(select_base_url=False)
        self._info(f"config: {default_env_file()}")
        self._load_cached_catalog()
        self.root.after(80, self._poll_queue)

    def _load_cached_catalog(self) -> None:
        """Startup: use the cached catalog when fresh, else the fallback."""
        import time

        from almurrib.providers.catalog import cached_models

        cached = cached_models(self._provider_id(), now_epoch=time.time())
        if cached is None:
            return  # _on_provider_changed already showed the fallback list
        models, source, _ = cached
        self._apply_models(models, source)
        self._info(f"using cached model catalog ({len(models)} models)")

    # ------------------------------------------------------------- UI layout

    def _build_ui(self) -> None:
        pad = {"padx": 6, "pady": 3}

        frm_game = Frame(self.root)
        frm_game.pack(fill=X, **pad)
        Label(frm_game, text="Game Folder:", width=14, anchor="w").pack(side=LEFT)
        game_entry = Entry(frm_game, textvariable=self.game_dir)
        game_entry.pack(side=LEFT, fill=X, expand=True)
        attach_editing(game_entry)
        Button(frm_game, text="اختيار مجلد اللعبة", command=self._pick_game).pack(side=RIGHT)

        frm_db = Frame(self.root)
        frm_db.pack(fill=X, **pad)
        Label(frm_db, text="Database:", width=14, anchor="w").pack(side=LEFT)
        db_entry = Entry(frm_db, textvariable=self.db_path)
        db_entry.pack(side=LEFT, fill=X, expand=True)
        attach_editing(db_entry)
        Button(frm_db, text="Browse…", command=self._pick_db).pack(side=RIGHT)

        frm_lang = Frame(self.root)
        frm_lang.pack(fill=X, **pad)
        Label(frm_lang, text="Source:").pack(side=LEFT)
        self.src_combo = Combobox(
            frm_lang, textvariable=self.source_lang, width=14,
            values=sorted(SOURCE_LANGS), state="readonly",
        )
        self.src_combo.pack(side=LEFT, padx=(2, 16))
        Label(frm_lang, text="Target:").pack(side=LEFT)
        self.tgt_combo = Combobox(
            frm_lang, textvariable=self.target_lang, width=14,
            values=sorted(TARGET_LANGS), state="readonly",
        )
        self.tgt_combo.pack(side=LEFT, padx=(2, 0))
        attach_editing(self.tgt_combo)

        frm_out = Frame(self.root)
        frm_out.pack(fill=X, **pad)
        Label(frm_out, text="Output Folder:", width=14, anchor="w").pack(side=LEFT)
        out_entry = Entry(frm_out, textvariable=self.output_dir)
        out_entry.pack(side=LEFT, fill=X, expand=True)
        attach_editing(out_entry)
        Button(frm_out, text="Browse…", command=self._pick_output).pack(side=RIGHT)

        frm_prov = LabelFrame(self.root, text="Provider Configuration")
        frm_prov.pack(fill=X, **pad)
        Label(frm_prov, text="Provider:", width=12, anchor="w").grid(
            row=0, column=0, sticky="w", padx=4)
        self.prov_combo = Combobox(
            frm_prov, textvariable=self.provider_name, state="readonly",
            values=[d.display_name for d in list_definitions()],
        )
        self.prov_combo.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        self.prov_combo.bind("<<ComboboxSelected>>",
                             lambda e: self._on_provider_changed())
        self._labeled_entry(frm_prov, "Base URL:", self.base_url, 1)
        Label(frm_prov, text="Model:", width=12, anchor="w").grid(
            row=2, column=0, sticky="w", padx=4)
        self.model_combo = Combobox(frm_prov, textvariable=self.model)
        self.model_combo.grid(row=2, column=1, sticky="ew", padx=4, pady=2)
        self.model_combo.bind("<KeyRelease>", lambda e: self._filter_models())
        self.model_combo.bind("<<ComboboxSelected>>",
                              lambda e: self._show_model_details())
        attach_editing(self.model_combo)
        self.models_source = StringVar(value="Models source: ● Static fallback")
        Label(frm_prov, textvariable=self.models_source, anchor="w").grid(
            row=3, column=1, sticky="ew", padx=4)
        self.model_details = StringVar(value="")
        Label(frm_prov, textvariable=self.model_details, anchor="w",
              wraplength=560, justify=LEFT).grid(
            row=4, column=1, sticky="ew", padx=4)
        self._labeled_entry(frm_prov, "API Key:", self.api_key, 5, secret=True)
        frm_prov.columnconfigure(1, weight=1)

        frm_pbtns = Frame(frm_prov)
        frm_pbtns.grid(row=6, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        Button(frm_pbtns, text="Test Connection",
               command=self._on_test_connection).pack(side=LEFT, padx=2)
        Button(frm_pbtns, text="Refresh Models",
               command=self._on_refresh_models).pack(side=LEFT, padx=2)
        Button(frm_pbtns, text="Save Configuration",
               command=self._save_config).pack(side=RIGHT, padx=2)

        frm_force = Frame(self.root)
        frm_force.pack(fill=X, **pad)
        from tkinter import Checkbutton
        Checkbutton(frm_force, text="Force retranslation (ignore TM/cache/translated)",
                    variable=self.force).pack(side=LEFT)

        frm_actions = Frame(self.root)
        frm_actions.pack(fill=X, **pad)
        self.btn_detect = Button(frm_actions, text="Detect", command=self._on_detect)
        self.btn_extract = Button(frm_actions, text="Extract", command=self._on_extract)
        self.btn_translate = Button(frm_actions, text="Translate", command=self._on_translate)
        self.btn_export = Button(frm_actions, text="Export", command=self._on_export)
        self.btn_clear = Button(frm_actions, text="Clear Translations",
                                command=self._on_clear)
        for b in (self.btn_detect, self.btn_extract, self.btn_translate,
                  self.btn_export, self.btn_clear):
            b.pack(side=LEFT, padx=3, expand=True, fill=X)

        self.btn_localize = Button(
            self.root, text="LOCALIZE GAME", command=self._on_localize,
            font=("Segoe UI", 11, "bold"),
        )
        self.btn_localize.pack(fill=X, padx=6, pady=6)
        self._action_buttons = [
            self.btn_detect, self.btn_extract, self.btn_translate,
            self.btn_export, self.btn_clear, self.btn_localize,
        ]

        self.progress = Progressbar(self.root, mode="determinate", maximum=100)
        self.progress.pack(fill=X, padx=6, pady=3)

        frm_log = LabelFrame(self.root, text="Log")
        frm_log.pack(fill=BOTH, expand=True, padx=6, pady=6)
        frm_logbtns = Frame(frm_log)
        frm_logbtns.pack(fill=X, padx=2, pady=2)
        Button(frm_logbtns, text="Copy Log", command=self._copy_log).pack(
            side=LEFT, padx=2)
        Button(frm_logbtns, text="Clear Log", command=self._clear_log).pack(
            side=LEFT, padx=2)
        self.log = Text(frm_log, state="disabled", wrap="word", height=10,
                        undo=True, maxundo=50)
        self.log.pack(fill=BOTH, expand=True)
        self._attach_log_menu()

    @staticmethod
    def _labeled_entry(parent, label, variable, row, *, secret: bool = False) -> Entry:
        Label(parent, text=label, width=12, anchor="w").grid(row=row, column=0, sticky="w", padx=4)
        entry = Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
        parent.columnconfigure(1, weight=1)
        if secret:
            entry.config(show="*")  # mask on screen; clipboard still works
        attach_editing(entry)
        return entry

    # ------------------------------------------------------------- log tools

    def _redact(self, text: str) -> str:
        """Strip secrets before text reaches the log or the clipboard."""
        from almurrib.core.reporting import redact_secrets

        return redact_secrets(text, [self.api_key.get()])

    def _attach_log_menu(self) -> None:
        menu = Menu(self.log, tearoff=0)
        menu.add_command(label="Copy", command=self._copy_selection)
        menu.add_command(label="Copy All", command=self._copy_log)
        menu.add_command(label="Select All", command=self._select_log_all)
        menu.add_separator()
        menu.add_command(label="Clear Log", command=self._clear_log)
        self.log.bind("<Button-3>",
                      lambda e: (self.log.focus_set(),
                                 menu.tk_popup(e.x_root, e.y_root)))

    def _log_text(self) -> str:
        return self.log.get("1.0", END)

    def _copy_selection(self) -> None:
        try:
            selected = self.log.get("sel.first", "sel.last")
        except TclError:
            return
        self.log.clipboard_clear()
        self.log.clipboard_append(self._redact(selected))

    def _copy_log(self) -> None:
        self.log.clipboard_clear()
        self.log.clipboard_append(self._redact(self._log_text()))
        self._info("log copied to clipboard (secrets redacted)")

    def _select_log_all(self) -> None:
        self.log.tag_add("sel", "1.0", END)

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", END)
        self.log.configure(state="disabled")

    # ------------------------------------------------------------- logging

    def _log(self, level: str, message: str) -> None:
        message = self._redact(message)
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

    def _pick_output(self) -> None:
        path = filedialog.askdirectory(title="Output Folder")
        if path:
            self.output_dir.set(path)

    # ------------------------------------------------- provider selection

    def _provider_id(self) -> str:
        """Resolve the provider Combobox display name back to its registry id."""
        wanted = self.provider_name.get().strip()
        for definition in list_definitions():
            if definition.display_name == wanted or definition.id == wanted:
                return definition.id
        return wanted or "openai_compat"

    def _source_code(self) -> str:
        return SOURCE_LANGS.get(self.source_lang.get(), "en")

    def _target_code(self) -> str:
        return TARGET_LANGS.get(self.target_lang.get(), "arabic")

    def _on_provider_changed(self, select_base_url: bool = True) -> None:
        """Changing provider updates base URL + model list, nothing else.

        The dropdown is NEVER left empty: a curated fallback list ships per
        provider until Refresh Models replaces it with the live catalog.
        """
        definition = get_definition(self._provider_id())
        if definition is None:
            return
        if select_base_url:
            self.base_url.set(definition.base_url)
        # A model id from another provider is meaningless here: drop the
        # fetched catalog and show this provider's fallback list instead.
        # The user's typed text is preserved (manual entry always works).
        self._models = []
        self._apply_fallback(silent=True)

    def _definition(self):
        return get_definition(self._provider_id())

    def _discovery_params(self) -> dict:
        definition = self._definition()
        if definition is None:
            raise AlMurribError(f"unknown provider '{self._provider_id()}'")
        return {
            "base_url": self.base_url.get().strip() or definition.base_url,
            "models_path": definition.models_path,
            "discovery": definition.discovery,
        }

    def _fetch_models_sync(self) -> list[ModelInfo]:
        """Blocking catalog fetch (always called from a worker thread)."""
        params = self._discovery_params()
        api_key = self.api_key.get().strip()
        definition = self._definition()
        if not api_key:
            if definition is not None and definition.local:
                api_key = "not-needed"  # local servers ignore the key
            else:
                raise AuthenticationError(
                    "no API key configured",
                    hint="enter the API key first, then Refresh Models.",
                )
        return fetch_models(api_key=api_key, timeout_seconds=30.0, **params)

    def _set_models_source(self, source: str) -> None:
        from almurrib.providers.discovery import SOURCE_BADGES

        self.models_source.set(
            f"Models source: ● {SOURCE_BADGES.get(source, source)}")

    def _apply_models(self, models: list[ModelInfo], source: str) -> None:
        self._models = models
        self._model_pool = [m.id for m in models]
        self.model_combo.configure(values=self._model_pool)
        self._set_models_source(source)
        self._show_model_details()

    def _apply_fallback(self, silent: bool = False) -> None:
        """Show the provider's curated ids when no live catalog is loaded."""
        from almurrib.providers.discovery import SOURCE_STATIC

        definition = self._definition()
        pool = list(definition.fallback_models) if definition else []
        self._model_pool = pool
        self.model_combo.configure(values=pool)
        self._set_models_source(SOURCE_STATIC)
        self._show_model_details()
        if pool and not silent:
            self._info(
                f"showing {len(pool)} known models for "
                f"{definition.display_name if definition else '?'} "
                "(Refresh Models for the live catalog)"
            )

    def _show_model_details(self) -> None:
        """Metadata line for the selected model id (Unknown, never guessed)."""
        wanted = self.model_combo.get().strip()
        for model in self._models:
            if model.id == wanted:
                self.model_details.set(model.details_line())
                return
        self.model_details.set("" if not wanted else
                                f"{wanted} • source: manual entry")

    def _filter_models(self) -> None:
        """Narrow the dropdown to what the user typed (manual text stays).

        Searches the live catalog when fetched, else the fallback list —
        typing a custom id never gets rewritten.
        """
        if not self._model_pool:
            return  # nothing listed: free manual entry, no filtering
        needle = self.model_combo.get().strip().lower()
        if not needle:
            self.model_combo.configure(values=self._model_pool)
            return
        hits = [mid for mid in self._model_pool if needle in mid.lower()]
        self.model_combo.configure(values=hits or self._model_pool)

    def _refresh_models_sync(self):
        """Priority-ordered catalog refresh (official → external → static)."""
        from almurrib.providers.catalog import refresh_models as _refresh

        params = self._discovery_params()
        api_key = self.api_key.get().strip()
        definition = self._definition()
        if not api_key:
            if definition is not None and definition.local:
                api_key = "not-needed"  # local servers ignore the key
            else:
                raise AuthenticationError(
                    "no API key configured",
                    hint="enter the API key first, then Refresh Models.",
                )
        result = _refresh(
            definition, api_key=api_key,
            base_url=params["base_url"], timeout_seconds=30.0,
        )
        return result

    def _on_refresh_models(self) -> None:
        def work() -> str:
            from almurrib.providers.catalog import store_models

            result = self._refresh_models_sync()
            if not result.models:
                # Never wipe a working catalog: surface the cause, keep pool.
                raise AlMurribError(result.error or "no models available")
            store_models(self._provider_id(), result.models, result.source,
                         result.models[0].retrieved_at)
            self._queue.put(("models", (result.models, result.source)))
            if result.error:
                self._queue.put(("info",
                                 f"note: {result.error} — showing fallback catalog"))
            shown = ", ".join(m.short_label() for m in result.models[:8])
            more = (f" (+{len(result.models) - 8} more)"
                    if len(result.models) > 8 else "")
            return f"{len(result.models)} models available: {shown}{more}"

        self._run_async("Refreshing models...", work)

    def _on_test_connection(self) -> None:
        def work() -> str:
            from almurrib.providers.discovery import SOURCE_LIVE

            models = self._fetch_models_sync()
            self._queue.put(("models", (models, SOURCE_LIVE)))
            definition = self._definition()
            name = definition.display_name if definition else self._provider_id()
            lines = [
                "Connection successful",
                f"API key valid ({name})",
                f"{len(models)} models available",
            ]
            return "\n".join(lines)

        self._run_async("Testing connection...", work)

    # ------------------------------------------------------------- config

    def _save_config(self) -> None:
        env_path = default_env_file()
        try:
            save_env_file(env_path, {
                ENV_PREFIX + "PROVIDER": self._provider_id(),
                ENV_PREFIX + "BASE_URL": self.base_url.get(),
                ENV_PREFIX + "MODEL": self.model.get(),
                ENV_PREFIX + "API_KEY": self.api_key.get(),
                ENV_PREFIX + "SOURCE_LANG": self._source_code(),
                ENV_PREFIX + "TARGET_LANG": self._target_code(),
                ENV_PREFIX + "DATABASE": self.db_path.get(),
                ENV_PREFIX + "OUTPUT_DIR": self.output_dir.get(),
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

        api_key = self.api_key.get().strip()
        if not api_key:
            raise AuthenticationError(
                "no API key configured",
                hint="enter the API key in the GUI (it is stored in the local .env on Save).",
            )
        config = ProviderConfig(
            provider=self._provider_id(),
            model=self.model.get().strip(),
            base_url=self.base_url.get().strip(),
            api_key=api_key,
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
                elif kind == "models":
                    models, source = payload
                    self._apply_models(models, source)
                    self._info(f"model list updated ({len(models)} models)")
                elif kind == "info":
                    self._info(payload)
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
                    pipeline, self._game_path(), db,
                    target_lang=self._target_code(),
                )
            return f"{len(entries)} entries extracted"

        self._run_async("Extracting text...", work)

    def _run_settings(self):
        """Fresh TM-reuse setting for each run (cheap file/env read)."""
        from almurrib.core.config import load_settings

        try:
            return load_settings().reuse_machine_tm
        except Exception:
            return False

    def _failure(self, stats) -> AlMurribError:
        provider_id = self._provider_id()
        return AlMurribError(
            format_translation_error(
                provider=provider_display_name(
                    provider_id, f"{provider_id}:{self.model.get()}"),
                base_url=self.base_url.get(),
                model=self.model.get(),
                stats=stats,
                retries=3,
            )
        )

    def _summary(self, stats) -> str:
        from almurrib.core.reporting import format_translation_summary

        return format_translation_summary(stats)

    def _on_translate(self) -> None:
        def work() -> str:
            provider = self._provider()
            force = bool(self.force.get())
            with Database(self._db()) as db:
                project = resolve_project(db, self._game_path())
                if project is None:
                    return "no stored project for this game — run Extract first"
                repo = EntryRepository(db)
                entries = repo.list(project_id=project.id)
                if not entries:
                    return "no entries stored — run Extract first"
                stats = translate_entries(
                    entries, db, provider,
                    source_lang=self._source_code(),
                    target_lang=self._target_code(),
                    project_id=project.id,
                    force=force,
                    reuse_machine_tm=self._run_settings(),
                    progress=self._progress_cb,
                )
            if stats.failed:
                # Surface the real cause, then the summary.
                raise self._failure(stats)
            return self._summary(stats)

        self._run_async("Translating...", work, determinate=True)

    def _on_clear(self) -> None:
        """Wipe this game's translations for a clean-slate comparison run."""
        from almurrib.core.workflow import clear_project_translations

        if not messagebox.askyesno(
            WINDOW_TITLE,
            "Clear all stored translations for this game?\n\n"
            "Source entries stay; obsolete history is preserved.\n"
            "Next Translate will call the provider fresh.",
        ):
            return

        def work() -> str:
            with Database(self._db()) as db:
                project = resolve_project(db, self._game_path())
                if project is None:
                    return "no stored project for this game — nothing to clear"
                count = clear_project_translations(db, project.id)
            return (f"cleared {count} translation(s) — point Output Folder "
                    f"at a fresh dir per model to compare runs side by side")

        self._run_async("Clearing translations...", work)

    def _on_export(self) -> None:
        def work() -> str:
            pipeline = LocalizationPipeline(adapters=default_adapters())
            with Database(self._db()) as db:
                project = resolve_project(db, self._game_path())
                written = export_translations(
                    pipeline, self._game_path(), db,
                    output_dir=Path(self.output_dir.get().strip() or "out"),
                    target_lang=self._target_code(),
                    project_id=project.id if project else None,
                )
            files = "; ".join(str(p) for p in written)
            return f"exported {len(written)} file(s): {files}"

        self._run_async("Exporting localization...", work)

    def _on_localize(self) -> None:
        def work() -> str:
            pipeline = LocalizationPipeline(adapters=default_adapters())
            provider = self._provider()
            force = bool(self.force.get())
            out_dir = Path(self.output_dir.get().strip() or "out")
            with Database(self._db()) as db:
                entries, project_id = extract_and_store(
                    pipeline, self._game_path(), db,
                    target_lang=self._target_code(),
                )
                stats = translate_entries(
                    entries, db, provider,
                    source_lang=self._source_code(),
                    target_lang=self._target_code(),
                    project_id=project_id,
                    force=force,
                    reuse_machine_tm=self._run_settings(),
                    progress=self._progress_cb,
                )
                if stats.failed:
                    raise self._failure(stats)
                written = export_translations(
                    pipeline, self._game_path(), db,
                    output_dir=out_dir,
                    target_lang=self._target_code(),
                    project_id=project_id,
                )
            return (
                f"{len(entries)} extracted; {stats.api_translated} translated via API; "
                f"{len(written)} file(s) exported to {out_dir}"
            )

        self._run_async("Running full localization...", work, determinate=True)


def main() -> None:
    """Launch the Almurrib GUI."""
    root = Tk()
    AlmurribApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
