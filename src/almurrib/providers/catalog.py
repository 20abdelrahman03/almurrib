"""Model catalog: live discovery first, maintained catalogs as fallback.

Source priority per provider (see ``registry.discovery_strategy``)::

    official live model API  ->  external catalog  ->  static fallback

* Official APIs answer "what can THIS key call" (authoritative).
* External catalogs (LiteLLM filtered API, Models.dev dump) answer "what
  exists" (metadata fallback, never confused with account access).
* Static fallback ids ship in the registry and are clearly labeled.

Results are file-cached (live 24h, external 7d) so the GUI never hits the
network on every paint; a failed refresh keeps the previous working
catalog. The cache holds model metadata only — never keys or secrets.
"""

from __future__ import annotations

import dataclasses
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from almurrib.core.errors import (
    AuthenticationError,
    InvalidResponseError,
    ProviderError,
)
from almurrib.providers.discovery import (
    SOURCE_LITELLM,
    SOURCE_LIVE,
    SOURCE_MODELS_DEV,
    SOURCE_STATIC,
    ModelInfo,
    fetch_models,
    utcnow_iso,
)
from almurrib.providers.registry import ProviderDefinition

MODELS_DEV_URL = "https://models.dev/api.json"
LITELLM_CATALOG_URL = "https://api.litellm.ai/model_catalog"

LIVE_TTL_SECONDS = 24 * 3600
EXTERNAL_TTL_SECONDS = 7 * 24 * 3600
LITELLM_MAX_PAGES = 3
CACHE_FILENAME = ".almurrib_model_cache.json"

# LiteLLM modes that are never translation candidates.
_NON_TEXT_MODES = frozenset({
    "image_generation",
    "embedding",
    "moderation",
    "audio_transcription",
    "audio_speech",
    "image_edit",
})


@dataclass
class RefreshResult:
    models: list[ModelInfo]
    source: str
    error: str | None = None  # non-fatal earlier failure (official failed)


def _get_json(url: str, *, timeout_seconds: float) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": "almurrib", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as resp:
            try:
                body = json.loads(resp.read().decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise InvalidResponseError(
                    f"catalog response was not valid JSON: {exc}"
                ) from exc
    except TimeoutError as exc:
        from almurrib.core.errors import ProviderTimeoutError

        raise ProviderTimeoutError(f"catalog request timed out: {exc}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise ProviderError(f"catalog network error: {reason}") from exc
    if not isinstance(body, dict):
        raise InvalidResponseError("catalog response JSON was not an object")
    return body


def _pricing(pricing: dict, *keys: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for key in keys:
        value = pricing.get(key)
        if isinstance(value, (int, float)):
            out[key] = float(value)
    return out


def fetch_litellm_models(
    catalog_id: str, *, provider_id: str, timeout_seconds: float = 30.0
) -> list[ModelInfo]:
    """Provider-filtered LiteLLM catalog (small pages, up to a fixed cap)."""
    from urllib.parse import quote

    models: list[ModelInfo] = []
    stamped = utcnow_iso()
    for page in range(1, LITELLM_MAX_PAGES + 1):
        body = _get_json(
            f"{LITELLM_CATALOG_URL}?provider={quote(catalog_id)}&page={page}",
            timeout_seconds=timeout_seconds,
        )
        data = body.get("data")
        if not isinstance(data, list):
            raise InvalidResponseError("LiteLLM catalog had no 'data' array")
        prefix = catalog_id + "/"
        for item in data:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            mode = item.get("mode")
            if isinstance(mode, str) and mode in _NON_TEXT_MODES:
                continue
            raw_id = item["id"]
            model_id = raw_id[len(prefix):] if raw_id.startswith(prefix) else raw_id
            if not model_id:
                continue
            costs = _pricing(item, "input_cost_per_token", "output_cost_per_token",
                             "cache_read_input_token_cost")
            models.append(ModelInfo(
                id=model_id,  # exact id sent to the provider
                provider=provider_id,
                context_length=item.get("max_input_tokens")
                if isinstance(item.get("max_input_tokens"), int) else None,
                reasoning=item.get("supports_reasoning")
                if isinstance(item.get("supports_reasoning"), bool) else None,
                tools=item.get("supports_function_calling")
                if isinstance(item.get("supports_function_calling"), bool) else None,
                json_support=item.get("supports_response_schema")
                if isinstance(item.get("supports_response_schema"), bool) else None,
                pricing=costs,
                status="deprecated" if item.get("deprecation_date") else None,
                source=SOURCE_LITELLM,
                retrieved_at=stamped,
            ))
        if not body.get("has_more"):
            break
    models.sort(key=lambda m: m.id.lower())
    return models


def fetch_models_dev_models(
    catalog_id: str, *, provider_id: str, timeout_seconds: float = 60.0
) -> list[ModelInfo]:
    """One provider section of the Models.dev dump (full file, cached)."""
    body = _get_json(MODELS_DEV_URL, timeout_seconds=timeout_seconds)
    section = body.get(catalog_id)
    if not isinstance(section, dict):
        raise InvalidResponseError(
            f"Models.dev has no provider section '{catalog_id}'")
    entries = section.get("models")
    if not isinstance(entries, dict):
        raise InvalidResponseError("Models.dev provider section had no 'models'")
    stamped = utcnow_iso()
    models: list[ModelInfo] = []
    for model_id, item in entries.items():
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        exact_id = item["id"]  # never transformed
        modalities = item.get("modalities") or {}
        limit = item.get("limit") or {}
        cost = item.get("cost") or {}
        models.append(ModelInfo(
            id=exact_id,
            display_name=item.get("name")
            if isinstance(item.get("name"), str) else None,
            provider=provider_id,
            context_length=limit.get("context")
            if isinstance(limit.get("context"), int) else None,
            input_modalities=tuple(modalities.get("input", []))
            if isinstance(modalities.get("input"), list) else None,
            output_modalities=tuple(modalities.get("output", []))
            if isinstance(modalities.get("output"), list) else None,
            reasoning=item.get("reasoning")
            if isinstance(item.get("reasoning"), bool) else None,
            tools=item.get("tool_call")
            if isinstance(item.get("tool_call"), bool) else None,
            json_support=item.get("structured_output")
            if isinstance(item.get("structured_output"), bool) else None,
            pricing=_pricing(cost, "input", "output", "cache_read"),
            source=SOURCE_MODELS_DEV,
            retrieved_at=stamped,
        ))
    models.sort(key=lambda m: m.id.lower())
    return models


def static_models(definition: ProviderDefinition) -> list[ModelInfo]:
    """Registry fallback ids, explicitly labeled (may go stale)."""
    stamped = utcnow_iso()
    return [
        ModelInfo(id=model_id, provider=definition.id,
                  source=SOURCE_STATIC, retrieved_at=stamped)
        for model_id in definition.fallback_models
    ]


def refresh_models(
    definition: ProviderDefinition,
    *,
    api_key: str,
    base_url: str,
    timeout_seconds: float = 30.0,
) -> RefreshResult:
    """Resolve the model list honoring source priority.

    Authentication failures always raise (the user must fix the key);
    other official-API failures fall through to external catalogs and
    finally the static fallback, carrying the first error along.
    """
    first_error: str | None = None
    if definition.discovery != "none":
        try:
            models = fetch_models(
                base_url=base_url,
                api_key=api_key,
                models_path=definition.models_path,
                discovery=definition.discovery,
                timeout_seconds=timeout_seconds,
            )
            return RefreshResult(models=_with_provider(models, definition.id),
                                 source=SOURCE_LIVE)
        except AuthenticationError:
            raise
        except Exception as exc:  # keep going: external, then static
            first_error = str(exc)

    catalog_id = definition.external_id or definition.id
    try:
        if definition.external_catalog == "litellm":
            models = fetch_litellm_models(
                catalog_id, provider_id=definition.id,
                timeout_seconds=timeout_seconds)
        elif definition.external_catalog == "models_dev":
            models = fetch_models_dev_models(
                catalog_id, provider_id=definition.id,
                timeout_seconds=max(timeout_seconds, 60.0))
        else:
            models = []
        if models:
            return RefreshResult(models=models,
                                 source=models[0].source, error=first_error)
    except Exception as exc:
        if first_error is None:
            first_error = str(exc)
    return RefreshResult(models=static_models(definition),
                         source=SOURCE_STATIC, error=first_error)


def _with_provider(models: list[ModelInfo], provider_id: str) -> list[ModelInfo]:
    return [
        dataclasses.replace(m, provider=m.provider or provider_id)
        for m in models
    ]


# ----- file cache ----------------------------------------------------------

def cache_path(base_dir: Path | None = None) -> Path:
    from almurrib.core.paths import app_base_dir

    return (base_dir or app_base_dir()) / CACHE_FILENAME


def load_cache(base_dir: Path | None = None) -> dict:
    try:
        return json.loads(cache_path(base_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache(entries: dict, base_dir: Path | None = None) -> None:
    """Persist model metadata only (never keys or secrets)."""
    path = cache_path(base_dir)
    try:
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    except OSError:
        pass  # cache is best-effort; the app works without it


def _ttl_for(source: str) -> int:
    return LIVE_TTL_SECONDS if source == SOURCE_LIVE else EXTERNAL_TTL_SECONDS


def cached_models(
    provider_id: str, *, now_epoch: float, base_dir: Path | None = None,
) -> tuple[list[ModelInfo], str, str] | None:
    """Fresh cached catalog as (models, source, retrieved_at), else None."""
    import time

    entry = load_cache(base_dir).get(provider_id)
    if not isinstance(entry, dict):
        return None
    try:
        retrieved = float(entry.get("retrieved_at_epoch", 0))
    except (TypeError, ValueError):
        return None
    source = str(entry.get("source") or SOURCE_STATIC)
    if now_epoch - retrieved > _ttl_for(source):
        return None  # stale: caller refreshes
    models = []
    for item in entry.get("models", []) or []:
        try:
            item = dict(item)
            for key in ("input_modalities", "output_modalities"):
                if isinstance(item.get(key), list):
                    item[key] = tuple(item[key])
            models.append(ModelInfo(**item))
        except TypeError:
            continue
    if not models:
        return None
    return models, source, entry.get("retrieved_at", "")


def store_models(
    provider_id: str, models: list[ModelInfo], source: str,
    retrieved_at: str, *, base_dir: Path | None = None,
) -> None:
    import time

    entries = load_cache(base_dir)
    entries[provider_id] = {
        "source": source,
        "retrieved_at": retrieved_at,
        "retrieved_at_epoch": time.time(),
        "models": [dataclasses.asdict(m) for m in models],
    }
    save_cache(entries, base_dir)
