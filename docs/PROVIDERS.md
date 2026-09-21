# Provider Matrix — Phase 1

How providers plug in: `providers/registry.py` holds one `ProviderDefinition`
per provider (id, display name, protocol, base URL, discovery strategy).
`openai_chat` definitions share the generic stdlib transport
(`providers/openai_compat.py`); only genuinely different wire protocols get
an adapter (`providers/cohere.py`). Adding a compatible provider = one
definition; the GUI discovers it automatically (no GUI changes).

Model discovery: provider key → **Refresh Models** → priority-ordered
resolution in `providers/catalog.py`:

```text
official live model API → external catalog → static fallback → manual entry
```

The model dropdown accepts manual ids as fallback
(local models, private deployments, new releases).

Before (or without) a fetch, each definition contributes a curated
`fallback_models` list so the dropdown is never empty — searchable by
typing, and clearly superseded once the live catalog loads. Fallbacks may
go stale; discovery is authoritative. The legacy `openai_compat` id is kept
as a first-class definition so early configs keep resolving and discovering
against their own Base URL.

## Catalog sources

| Source | Endpoint | Payload | What it answers |
|---|---|---|---|
| Live provider API | `GET {base_url}/models` (Cohere: `/v1/models?endpoint=chat`) | tiny | what THIS key can call (authoritative) |
| LiteLLM catalog | `GET https://api.litellm.ai/model_catalog?provider=<id>` | ~40–100 KB, provider-filtered | what exists (metadata fallback) |
| Models.dev | `GET https://models.dev/api.json` (full dump, cached) | ~4.7 MB, 222 providers | what exists (modalities, releases, costs) |
| Static fallback | registry `fallback_models` | zero network | always-available ids, may go stale |

Authentication failures always surface (never masked by a fallback); other
official-API failures fall through to external catalogs, then static, with
the first error kept visible. A failed refresh never wipes a working list.
Catalogs are file-cached (live 24h, external 7d) at
`.almurrib_model_cache.json` next to the app — metadata only, never keys.
The GUI badge shows the source: Live provider API / Models.dev / LiteLLM
catalog / Static fallback. Catalog metadata is NOT account access: a listed
model may still be disabled for a given key — live discovery decides that.

## Provider / discovery matrix

| Provider | Live Discovery | Models.dev | LiteLLM | Fallback | Status |
|---|---|---|---|---|---|
| OpenRouter | yes | — | yes | yes | verified |
| TokenRouter | yes | yes | — | yes | verified |
| Agent Router | yes | yes | — | yes | verified |
| OpenAI | yes | — | yes | yes | verified |
| Gemini | yes | — | yes (`gemini`) | yes | verified (transport) |
| Kimi (Moonshot) | yes | — | yes (`moonshot`) | yes | UNVERIFIED |
| DeepSeek | yes | — | yes | yes | verified |
| Groq | yes | — | yes | yes | verified |
| Together AI | yes | — | yes (`together_ai`) | yes | UNVERIFIED |
| Fireworks AI | yes | — | yes (`fireworks_ai`) | yes | UNVERIFIED |
| DeepInfra | yes | — | yes | yes | verified |
| Cerebras | yes | — | yes | yes | UNVERIFIED |
| SambaNova | yes | — | yes | yes | UNVERIFIED |
| Mistral | yes | — | yes | yes | UNVERIFIED |
| xAI (Grok) | yes | — | yes | yes | UNVERIFIED |
| Hugging Face | yes | yes | — | yes | UNVERIFIED |
| Ollama (local) | yes | — | yes | yes | verified |
| llama.cpp (local) | yes | — | — | yes | UNVERIFIED |
| vLLM (local) | yes | — | — | yes | UNVERIFIED |
| NVIDIA NIM (local) | yes | yes (`nvidia`) | — | yes | verified |
| Cohere | yes (native) | — | yes | yes | verified |
| Anthropic | via router | — | via router | yes | definition only |
| OpenAI-Compatible (custom) | yes (own URL) | — | — | manual | legacy compat |

"Live Discovery: yes" means the provider exposes the endpoint and our
transport speaks it (mock-verified offline); only OpenRouter has proven a
real 75/75 translation run. Model ids are never transformed: the dropdown
shows the exact id sent to the provider.

`verified` = endpoint + auth + listing + chat shape checked against the
provider's current official docs (Sept 2026). Anything else is marked
`UNVERIFIED` — usable through the same transport, but not doc-checked.

## Definitions

| Provider | Protocol | Base URL | Discovery | JSON mode | Status |
|---|---|---|---|---|---|
| OpenRouter | OpenAI-compatible | `https://openrouter.ai/api/v1` | yes (rich: ctx, params, pricing) | model-dependent | verified |
| TokenRouter | OpenAI-compatible | `https://api.tokenrouter.io/v1` | yes | model-dependent (upstream decides) | verified |
| Agent Router | OpenAI-compatible | `https://agent-router.net/aggregate/openai/v1` | yes | model-dependent | verified |
| OpenAI | OpenAI-compatible | `https://api.openai.com/v1` | yes | yes | verified |
| DeepSeek | OpenAI-compatible | `https://api.deepseek.com/v1` | yes | model-dependent | verified |
| Groq | OpenAI-compatible | `https://api.groq.com/openai/v1` | yes | yes | verified |
| DeepInfra | OpenAI-compatible | `https://api.deepinfra.com/v1/openai` | yes | model-dependent | verified |
| Cohere | **native** (`POST /v1/chat`) | `https://api.cohere.com` | yes (`?endpoint=chat`, ctx + features) | model-dependent | verified |
| Ollama (local) | OpenAI-compatible | `http://localhost:11434/v1` | yes | yes | verified |
| NVIDIA NIM (local) | OpenAI-compatible | `http://localhost:8000/v1` | yes | model-dependent | verified |
| Gemini | OpenAI-compatible endpoint | `https://generativelanguage.googleapis.com/v1beta/openai` | yes | model-dependent | UNVERIFIED |
| Kimi (Moonshot) | OpenAI-compatible | `https://api.moonshot.ai/v1` | yes | model-dependent | UNVERIFIED |
| Together AI | OpenAI-compatible | `https://api.together.xyz/v1` | yes | model-dependent | UNVERIFIED |
| Fireworks AI | OpenAI-compatible | `https://api.fireworks.ai/inference/v1` | yes | model-dependent | UNVERIFIED |
| Cerebras | OpenAI-compatible | `https://api.cerebras.ai/v1` | yes | model-dependent | UNVERIFIED |
| SambaNova | OpenAI-compatible | `https://api.sambanova.ai/v1` | yes | model-dependent | UNVERIFIED |
| Mistral | OpenAI-compatible | `https://api.mistral.ai/v1` | yes | model-dependent | UNVERIFIED |
| xAI (Grok) | OpenAI-compatible | `https://api.x.ai/v1` | yes | model-dependent | UNVERIFIED |
| Hugging Face Providers | OpenAI-compatible | `https://router.huggingface.co/v1` | yes | model-dependent | UNVERIFIED |
| llama.cpp (local) | OpenAI-compatible | `http://localhost:8080/v1` | yes | model-dependent | UNVERIFIED |
| vLLM (local) | OpenAI-compatible | `http://localhost:8000/v1` | yes | model-dependent | UNVERIFIED |
| Anthropic | none (native Messages API) | via router | via router | via router | definition only — native adapter is future work; use OpenRouter/TokenRouter/Agent Router with a Claude model id |

## Transport behavior (all chat providers)

* `POST {base_url}/chat/completions` (Cohere: `POST {base_url}/v1/chat`),
  `Authorization: Bearer <key>`, stdlib HTTP only.
* `response_format: json_object` is sent unless the config says otherwise;
  a `400` refusing it triggers **one retry without it** (common on routers
  fronting non-JSON models).
* A malformed batch falls back to individual requests; per-item outcomes are
  counted (`fallback_calls`) and missing ids are reported, never dropped.
* Bounded exponential backoff on 429/5xx/timeouts; 401/403/404 fail fast
  with the provider's own message (key never included).

## Cohere specifics

* Chat request v2 `{model, messages, response_format}` (system message
  replaces the old `preamble`); reply text at `message.content[].text`,
  parsed against the same strict batch-JSON contract.
* Automatic version routing: a 400 demanding the other API version retries
  once there (current models require v2; legacy ones may need v1).
* Discovery reports `context_length` and `features` (`json_mode` mapped to
  the JSON capability flag shown in the GUI).
* `command-a-translate-*` is Cohere's translation-specialized family
  (Arabic included) — selectable like any discovered model, never hard-coded.

## Local providers

Ollama / llama.cpp / vLLM / NIM expose the same OpenAI-compatible shape on
localhost. Any non-empty key is accepted where the server ignores auth.
Manual model ids always work (discovery is best-effort on local servers).
