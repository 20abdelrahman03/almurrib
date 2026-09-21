"""Provider registry: data-driven provider definitions.

Adding a provider that speaks the OpenAI chat-completions shape means adding
one ``ProviderDefinition`` here — no GUI or Core changes. Only providers
whose wire protocol genuinely differs (Cohere, Anthropic) need a dedicated
adapter; everything else reuses the generic transport.

``verified`` records whether the endpoint/shape below was checked against
the provider's current official documentation (2026-09) rather than memory.
Unverified entries are still usable (same generic transport) but the docs
matrix flags them honestly.

``fallback_models`` are curated ids shown in the model dropdown when no live
catalog was fetched (offline, no key, discovery failed, or before the first
fetch). Refresh Models is authoritative and replaces them; they may go stale.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderDefinition:
    """Static description of one AI provider."""

    id: str  # short id used in config/GUI/factory
    display_name: str  # human label in the GUI
    protocol: str  # "openai_chat" | "cohere" | "anthropic"
    base_url: str  # API root WITHOUT the endpoint suffix
    models_path: str = "/models"  # discovery path appended to base_url
    discovery: str = "openai"  # "openai" | "cohere" | "none"
    auth: str = "bearer"  # how the API key travels
    json_object: str = "model-dependent"  # "yes" | "no" | "model-dependent"
    local: bool = False  # self-hosted: key optional, discovery best-effort
    verified: bool = False  # checked against official docs (see module doc)
    notes: str = ""
    extra: dict[str, str] = field(default_factory=dict)
    # Curated fallback model ids shown when no live catalog was fetched
    # (offline, no key, discovery failed). Refresh Models is authoritative;
    # these may go stale and are clearly superseded on fetch.
    fallback_models: list[str] = field(default_factory=list)
    # External metadata fallback when the official model API is unreachable:
    # "litellm" (provider-filtered, small), "models_dev" (full dump, cached),
    # or "none" (static fallback + manual entry only).
    external_catalog: str = "litellm"
    # Provider key inside the external catalog (defaults to this id).
    external_id: str = ""


# Discovery strategy order, resolved per definition (PART: explicit policy):
# official live model API -> external catalog -> static fallback -> manual.
OFFICIAL_API = "official_api"
MODELS_DEV = "models_dev"
LITELLM_CATALOG = "litellm_catalog"
STATIC_FALLBACK = "static_fallback"


def discovery_strategy(definition: ProviderDefinition) -> list[str]:
    """Ordered strategy names for a provider (explicit, data-driven)."""
    if definition.discovery == "none":
        return [STATIC_FALLBACK]
    steps = [OFFICIAL_API]
    if definition.external_catalog == "models_dev":
        steps.append(MODELS_DEV)
    elif definition.external_catalog == "litellm":
        steps.append(LITELLM_CATALOG)
    elif definition.external_catalog != "none":
        raise ValueError(
            f"unknown external catalog '{definition.external_catalog}'"
        )
    steps.append(STATIC_FALLBACK)
    return steps


PROVIDERS: dict[str, ProviderDefinition] = {
    # -- legacy id (early Phase 1 configs) --------------------------------
    "openai_compat": ProviderDefinition(
        id="openai_compat",
        display_name="OpenAI-Compatible (custom URL)",
        protocol="openai_chat",
        base_url="https://api.openai.com/v1",
        discovery="openai",
        json_object="model-dependent",
        verified=False,
        notes="Legacy id kept for early configs; discovery runs against "
        "your own Base URL. Prefer a named provider below.",
    ),
    # -- aggregators / routers -------------------------------------------
    "openrouter": ProviderDefinition(
        id="openrouter",
        display_name="OpenRouter",
        protocol="openai_chat",
        base_url="https://openrouter.ai/api/v1",
        discovery="openai",
        json_object="model-dependent",
        verified=True,
        notes="Unified gateway. Rich /models (context_length, "
        "supported_parameters incl. response_format, pricing). Optional "
        "HTTP-Referer / X-Title attribution headers (not sent).",
        fallback_models=[
            "qwen/qwen3-30b-a3b:free",
            "deepseek/deepseek-chat",
            "google/gemini-2.0-flash-001",
            "openai/gpt-4o-mini",
            "anthropic/claude-sonnet-4",
        ],
    ),
    "tokenrouter": ProviderDefinition(
        id="tokenrouter",
        display_name="TokenRouter",
        protocol="openai_chat",
        base_url="https://api.tokenrouter.io/v1",
        discovery="openai",
        external_catalog="models_dev",
        json_object="model-dependent",
        verified=True,
        notes="BYOK gateway (keys look like tr_...). JSON mode support "
        "depends on the routed upstream (Anthropic/Gemini routes lack it); "
        "the transport retries without response_format on refusal.",
        fallback_models=[
            "openai/gpt-4o-mini",
            "auto",
            "auto:balance",
        ],
    ),
    "agentrouter": ProviderDefinition(
        id="agentrouter",
        display_name="Agent Router",
        protocol="openai_chat",
        base_url="https://agent-router.net/aggregate/openai/v1",
        discovery="openai",
        external_catalog="models_dev",
        json_object="model-dependent",
        verified=True,
        notes="agent-router.net AI Aggregate surface (keys like sk-tp-...). "
        "Gateway surface https://agent-router.net/gateway/openai/v1 needs a "
        "configured upstream/BYOK. agentrouter.org exposes a compatible "
        "https://agentrouter.org/v1 — override Base URL if you use it.",
        extra={"alt_base_url": "https://agent-router.net/gateway/openai/v1"},
        fallback_models=[
            "gpt-4o-mini",
            "claude-sonnet-4-5",
            "deepseek-chat",
        ],
    ),
    # -- major model providers (OpenAI-compatible transports) -------------
    "openai": ProviderDefinition(
        id="openai",
        display_name="OpenAI",
        protocol="openai_chat",
        base_url="https://api.openai.com/v1",
        discovery="openai",
        json_object="yes",
        verified=True,
        fallback_models=[
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1-mini",
            "gpt-4.1",
        ],
    ),
    "gemini": ProviderDefinition(
        id="gemini",
        display_name="Google Gemini (OpenAI-compatible)",
        protocol="openai_chat",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        discovery="openai",
        json_object="model-dependent",
        verified=False,
        notes="Gemini's OpenAI-compatible endpoint. Native Gemini REST "
        "differs; use this endpoint for the generic transport.",
        fallback_models=[
            "gemini-2.0-flash",
            "gemini-2.5-flash",
        ],
    ),
    "kimi": ProviderDefinition(
        id="kimi",
        display_name="Kimi (Moonshot)",
        protocol="openai_chat",
        base_url="https://api.moonshot.ai/v1",
        discovery="openai",
        external_id="moonshot",
        json_object="model-dependent",
        verified=False,
        fallback_models=[
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "kimi-k2",
        ],
    ),
    "deepseek": ProviderDefinition(
        id="deepseek",
        display_name="DeepSeek",
        protocol="openai_chat",
        base_url="https://api.deepseek.com/v1",
        discovery="openai",
        json_object="model-dependent",
        verified=True,
        notes="OpenAI-compatible /v1; reasoning models also return "
        "reasoning_content (ignored by the parser).",
        fallback_models=[
            "deepseek-chat",
            "deepseek-reasoner",
        ],
    ),
    "groq": ProviderDefinition(
        id="groq",
        display_name="Groq",
        protocol="openai_chat",
        base_url="https://api.groq.com/openai/v1",
        discovery="openai",
        json_object="yes",
        verified=True,
        notes="Note the /openai path segment (not bare /v1).",
        fallback_models=[
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-llama-70b",
        ],
    ),
    "together": ProviderDefinition(
        id="together",
        display_name="Together AI",
        protocol="openai_chat",
        base_url="https://api.together.xyz/v1",
        discovery="openai",
        external_id="together_ai",
        json_object="model-dependent",
        verified=False,
        fallback_models=[
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "deepseek-ai/DeepSeek-V3",
        ],
    ),
    "fireworks": ProviderDefinition(
        id="fireworks",
        display_name="Fireworks AI",
        protocol="openai_chat",
        base_url="https://api.fireworks.ai/inference/v1",
        discovery="openai",
        external_id="fireworks_ai",
        json_object="model-dependent",
        verified=False,
        fallback_models=[
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
        ],
    ),
    "deepinfra": ProviderDefinition(
        id="deepinfra",
        display_name="DeepInfra",
        protocol="openai_chat",
        base_url="https://api.deepinfra.com/v1/openai",
        discovery="openai",
        json_object="model-dependent",
        verified=True,
        notes="Note the /v1/openai path segment.",
        fallback_models=[
            "deepseek-ai/DeepSeek-V3",
            "meta-llama/Meta-Llama-3.1-70B-Instruct",
        ],
    ),
    "cerebras": ProviderDefinition(
        id="cerebras",
        display_name="Cerebras",
        protocol="openai_chat",
        base_url="https://api.cerebras.ai/v1",
        discovery="openai",
        json_object="model-dependent",
        verified=False,
        fallback_models=[
            "llama3.3-70b",
            "qwen-3-32b",
        ],
    ),
    "sambanova": ProviderDefinition(
        id="sambanova",
        display_name="SambaNova",
        protocol="openai_chat",
        base_url="https://api.sambanova.ai/v1",
        discovery="openai",
        json_object="model-dependent",
        verified=False,
        notes="Official SDK confirms OpenAI-compatible chat completions.",
        fallback_models=[
            "Meta-Llama-3.3-70B-Instruct",
        ],
    ),
    "mistral": ProviderDefinition(
        id="mistral",
        display_name="Mistral (La Plateforme)",
        protocol="openai_chat",
        base_url="https://api.mistral.ai/v1",
        discovery="openai",
        json_object="model-dependent",
        verified=False,
        fallback_models=[
            "mistral-large-latest",
            "mistral-small-latest",
        ],
    ),
    "xai": ProviderDefinition(
        id="xai",
        display_name="xAI (Grok)",
        protocol="openai_chat",
        base_url="https://api.x.ai/v1",
        discovery="openai",
        json_object="model-dependent",
        verified=False,
        fallback_models=[
            "grok-4",
            "grok-3-mini",
        ],
    ),
    "huggingface": ProviderDefinition(
        id="huggingface",
        display_name="Hugging Face Inference Providers",
        protocol="openai_chat",
        base_url="https://router.huggingface.co/v1",
        discovery="openai",
        external_catalog="models_dev",
        json_object="model-dependent",
        verified=False,
        notes="OpenAI-compatible router over many inference providers; "
        "model availability varies per provider.",
        fallback_models=[
            "deepseek-ai/DeepSeek-V3",
            "meta-llama/Meta-Llama-3.1-70B-Instruct",
        ],
    ),
    # -- native-protocol providers ----------------------------------------
    "cohere": ProviderDefinition(
        id="cohere",
        display_name="Cohere",
        protocol="cohere",
        base_url="https://api.cohere.com",
        models_path="/v1/models?endpoint=chat&page_size=200",
        discovery="cohere",
        json_object="model-dependent",
        verified=True,
        notes="Native API: v2/chat primary (messages + response_format), "
        "automatic one-shot fallback to v1/chat for legacy models. "
        "Command A Translate is translation-specialized incl. Arabic. "
        "Discovery exposes context_length and features (json_mode).",
        fallback_models=[
            "command-a-translate-08-2025",
            "command-a-03-2025",
            "command-r7b-12-2024",
            "command-a-plus-05-2026",
        ],
    ),
    "anthropic": ProviderDefinition(
        id="anthropic",
        display_name="Anthropic (via router)",
        protocol="openai_chat",
        base_url="https://openrouter.ai/api/v1",
        discovery="openai",
        json_object="model-dependent",
        verified=False,
        notes="Anthropic has no first-party OpenAI-compatible endpoint; use "
        "a router (OpenRouter/TokenRouter/Agent Router) with a Claude model "
        "id. A native Messages-API adapter is future work.",
        fallback_models=[
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
        ],
    ),
    # -- local / self-hosted ----------------------------------------------
    "ollama": ProviderDefinition(
        id="ollama",
        display_name="Ollama (local)",
        protocol="openai_chat",
        base_url="http://localhost:11434/v1",
        discovery="openai",
        json_object="yes",
        local=True,
        verified=True,
        notes="API key required by the client shape but ignored; any "
        "non-empty value works. JSON mode supported. Pull models first "
        "(`ollama pull ...`).",
        fallback_models=[
            "llama3.2",
            "qwen3",
            "mistral",
        ],
    ),
    "llamacpp": ProviderDefinition(
        id="llamacpp",
        display_name="llama.cpp server (local)",
        protocol="openai_chat",
        base_url="http://localhost:8080/v1",
        discovery="openai",
        external_catalog="none",
        json_object="model-dependent",
        local=True,
        verified=False,
        notes="llama.cpp --server OpenAI-compatible endpoint. JSON-mode "
        "support depends on server version/flags; the transport falls back "
        "to individual requests and plain-text retries automatically.",
        fallback_models=[
            "default",
        ],
    ),
    "vllm": ProviderDefinition(
        id="vllm",
        display_name="vLLM server (local)",
        protocol="openai_chat",
        base_url="http://localhost:8000/v1",
        discovery="openai",
        external_catalog="none",
        json_object="model-dependent",
        local=True,
        verified=False,
        notes="vLLM OpenAI-compatible server (also the engine behind "
        "NVIDIA NIM containers).",
        fallback_models=[
            "default",
        ],
    ),
    "nim": ProviderDefinition(
        id="nim",
        display_name="NVIDIA NIM (local)",
        protocol="openai_chat",
        base_url="http://localhost:8000/v1",
        discovery="openai",
        external_catalog="models_dev",
        external_id="nvidia",
        json_object="model-dependent",
        local=True,
        verified=True,
        notes="NIM containers expose the vLLM OpenAI-compatible API incl. "
        "GET /v1/models. Cloud NIM uses https://integrate.api.nvidia.com/v1 "
        "— override Base URL for cloud.",
        extra={"cloud_base_url": "https://integrate.api.nvidia.com/v1"},
        fallback_models=[
            "meta/llama-3.1-8b-instruct",
        ],
    ),
}


def get_definition(provider_id: str) -> ProviderDefinition | None:
    return PROVIDERS.get(provider_id)


def list_definitions(*, local_only: bool = False) -> list[ProviderDefinition]:
    defs = [d for d in PROVIDERS.values() if not local_only or d.local]
    return sorted(defs, key=lambda d: d.display_name.lower())


def preset_base_url(provider_id: str) -> str | None:
    definition = get_definition(provider_id)
    return definition.base_url if definition else None
