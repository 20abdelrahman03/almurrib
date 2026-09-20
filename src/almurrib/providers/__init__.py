"""Concrete translation providers.

The Core never imports from here directly; the CLI/factory wires providers
in. Adding a provider = implement TranslationProvider + register it in
``factory.py``. No core changes needed.
"""

from almurrib.providers.factory import build_provider
from almurrib.providers.openai_compat import OpenAICompatibleProvider

__all__ = ["OpenAICompatibleProvider", "build_provider"]
