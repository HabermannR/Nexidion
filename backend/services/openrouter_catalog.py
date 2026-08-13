"""Small, failure-tolerant view of the OpenRouter model catalog."""

import json
import os
import threading
import time
from urllib.request import Request, urlopen


DEFAULT_CURATED_MODELS = (
    ("deepseek/deepseek-v4-flash-0731", "DeepSeek V4 Flash"),
    ("qwen/qwen3.5-flash-02-23", "Qwen 3.5 Flash"),
    ("openai/gpt-5.6-luna", "GPT-5.6 Luna"),
    ("minimax/minimax-m3", "MiniMax M3"),
    ("google/gemini-3.7-flash", "Gemini 3.7 Flash"),
    ("z-ai/glm-5.2", "GLM 5.2"),
    ("deepseek/deepseek-v4-pro-0813", "DeepSeek V4 Pro"),
    ("openai/gpt-5.6-terra", "GPT-5.6 Terra"),
    ("anthropic/claude-sonnet-5", "Claude Sonnet 5"),
    ("openai/gpt-5.6-sol", "GPT-5.6 Sol"),
)

_cache = {"expires_at": 0.0, "models": None}
_lock = threading.Lock()


def _curated_models():
    configured = os.environ.get("OPENROUTER_CURATED_MODELS", "").strip()
    if not configured:
        return DEFAULT_CURATED_MODELS
    ids = [model.strip() for model in configured.split(",") if model.strip()][:10]
    return tuple((model, model) for model in ids)


def _price_per_million(value):
    try:
        return round(float(value) * 1_000_000, 6)
    except (TypeError, ValueError):
        return None


def _tier(input_price, output_price):
    if input_price is None or output_price is None:
        return None
    if input_price <= 1 and output_price <= 5:
        return "Economy"
    if input_price <= 5 and output_price <= 20:
        return "Balanced"
    return "Premium"


def _fallback():
    return [
        {"id": model_id, "name": name, "input_price": None,
         "output_price": None, "price_tier": None}
        for model_id, name in _curated_models()
    ]


def _fetch_catalog():
    headers = {"Accept": "application/json", "User-Agent": "Nexidion/4.3"}
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request("https://openrouter.ai/api/v1/models", headers=headers)
    with urlopen(request, timeout=3) as response:  # nosec: fixed HTTPS endpoint
        return json.load(response).get("data", [])


def get_curated_models():
    """Return at most ten curated models, enriched with cached catalog prices."""
    now = time.monotonic()
    if _cache["models"] is not None and now < _cache["expires_at"]:
        return _cache["models"]

    with _lock:
        now = time.monotonic()
        if _cache["models"] is not None and now < _cache["expires_at"]:
            return _cache["models"]
        try:
            catalog = {item.get("id"): item for item in _fetch_catalog()}
            models = []
            for model_id, fallback_name in _curated_models():
                item = catalog.get(model_id, {})
                pricing = item.get("pricing") or {}
                input_price = _price_per_million(pricing.get("prompt"))
                output_price = _price_per_million(pricing.get("completion"))
                models.append({
                    "id": model_id,
                    "name": item.get("name") or fallback_name,
                    "input_price": input_price,
                    "output_price": output_price,
                    "price_tier": _tier(input_price, output_price),
                })
        except Exception:
            models = _fallback()

        ttl = max(30, int(os.environ.get("OPENROUTER_CATALOG_CACHE_SECONDS", "300")))
        _cache.update(models=models, expires_at=time.monotonic() + ttl)
        return models
