"""Minimal Tkinter desktop GUI for Almurrib (frontend only).

The GUI contains no localization logic — it calls the existing
core/workflow/provider services. Long operations run on a background
thread so the window stays responsive.
"""

from almurrib.gui.app import AlmurribApp, main

__all__ = ["AlmurribApp", "main"]
