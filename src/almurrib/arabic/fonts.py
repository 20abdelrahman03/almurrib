"""Font/resource foundation (metadata first, injection later).

Phase 2-first-half scope is deliberately narrow: represent font assets,
discover local files, and define the packaging strategy — NOT engine
injection, NOT downloads, NOT license clearance (each font needs its own
review before bundling; see docs/ARABIC_LAYER.md).

Investigated candidates (project plan): Vazirmatn, Lalezar, Noto Naskh,
Cairo, Amiri — all OFL-licensed upstream, but nothing is vendored until a
per-font review records version + source + attribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FontAsset:
    """One font file with its packaging metadata."""

    name: str  # display name, e.g. "Vazirmatn Regular"
    path: Path  # absolute path to the font file
    format: str  # "ttf" | "otf" | "woff" | ...
    license: str = "Unknown"  # NEVER guessed: Unknown until reviewed
    family: str | None = None
    weight: str | None = None
    style: str | None = None
    source: str | None = None  # where it was obtained (URL or "system")

    def exists(self) -> bool:
        return self.path.is_file()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": str(self.path),
            "format": self.format,
            "license": self.license,
            "family": self.family,
            "weight": self.weight,
            "style": self.style,
            "source": self.source,
        }


_FONT_SUFFIXES = {".ttf": "ttf", ".otf": "otf", ".woff": "woff", ".woff2": "woff2"}


class FontMetrics:
    """Real advance-width measurement via fontTools (pure Python).

    Reads ``hmtx`` advances scaled to ``size`` pixels. Missing glyphs fall
    back to the ``.notdef`` advance (or the average); :meth:`has_glyph`
    exposes coverage so callers can detect tofu before rendering.
    Variable fonts measure at their default instance. Not a shaper:
    joining/positioning stay the renderer's job.
    """

    def __init__(self, font_path: Path | str, *, size: int = 16) -> None:
        from fontTools.ttLib import TTFont

        if size <= 0:
            raise ValueError(f"font size must be positive, got {size!r}")
        path = Path(font_path)
        if not path.is_file():
            raise FileNotFoundError(f"font file not found: {path}")
        try:
            self._font = TTFont(str(path), lazy=True)
            self._advances = self._font["hmtx"].metrics
            self._cmap = self._font.getBestCmap()
            self._units = self._font["head"].unitsPerEm
        except Exception as exc:
            raise ValueError(f"cannot read font metrics from {path}: {exc}") from exc
        if not self._units:
            raise ValueError(f"font has zero unitsPerEm: {path}")
        self.path = path
        self.size = size
        self._cache: dict[str, int] = {}
        entries = list(self._advances.items())
        notdef = dict(entries).get(".notdef", (0, 0))[0]
        average = sum(a for _, (a, _) in entries) / len(entries) if entries else 0
        self._fallback = round(
            (notdef or average) * size / self._units) or max(1, size // 2)

    def has_glyph(self, char: str) -> bool:
        """True when the font maps this character (no tofu expected)."""
        return ord(char) in self._cmap

    def glyph_width(self, char: str) -> int:
        """Advance width of one character in pixels (fallback if missing)."""
        if char in self._cache:
            return self._cache[char]
        glyph = self._cmap.get(ord(char))
        if glyph is None:
            width = self._fallback
        else:
            advance = self._advances.get(glyph, (0, 0))[0]
            width = round(advance * self.size / self._units) or self._fallback
        self._cache[char] = width
        return width

    def width_of(self, text: str) -> int:
        """Sum of advances (implements the TextMetrics protocol)."""
        return sum(self.glyph_width(char) for char in text)

    def line_height(self) -> int:
        """hhea ascent-descent scaled to size (line box, not shaping)."""
        try:
            hhea = self._font["hhea"]
            return round((hhea.ascent - hhea.descent) * self.size / self._units)
        except Exception:
            return self.size

    def close(self) -> None:
        try:
            self._font.close()
        except Exception:
            pass


class FontRegistry:
    """Local font discovery + manifest (no downloads, no injection)."""

    def __init__(self) -> None:
        self._assets: list[FontAsset] = []

    def register(self, asset: FontAsset) -> FontAsset:
        self._assets.append(asset)
        return asset

    def scan(self, directory: Path | str) -> list[FontAsset]:
        """Register every font file under a directory (deterministic order)."""
        found: list[FontAsset] = []
        for path in sorted(Path(directory).rglob("*")):
            if not path.is_file():
                continue
            fmt = _FONT_SUFFIXES.get(path.suffix.lower())
            if fmt is None:
                continue
            found.append(self.register(FontAsset(
                name=path.stem, path=path.resolve(), format=fmt,
                source=f"local:{path.resolve().parent}",
            )))
        return found

    def list(self, *, family: str | None = None) -> list[FontAsset]:
        if family is None:
            return list(self._assets)
        return [a for a in self._assets if (a.family or "").lower() == family.lower()]

    def manifest(self) -> dict:
        """Packaging manifest: what would ship with the app."""
        return {
            "format": "almurrib-fonts",
            "format_version": 1,
            "fonts": [a.to_dict() for a in self._assets],
        }

    def __len__(self) -> int:
        return len(self._assets)
