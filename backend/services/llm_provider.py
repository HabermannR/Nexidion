from __future__ import annotations

import os

from openai import OpenAI


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GENERATIVE_PROVIDERS = {"local", "openai", "openrouter"}


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is not configured.")
    return value


def client_and_model(provider: str, requested_model: str | None = None) -> tuple[OpenAI, str]:
    """Build an OpenAI-compatible client without exposing provider credentials.

    OpenRouter model identifiers are intentionally treated as opaque strings. This
    supports routed and ``:free`` model slugs without coupling Nexidion to a catalog
    that changes independently of an application release.
    """
    if provider == "local":
        client = OpenAI(
            base_url=_required_env("LOCAL_LLM_URL"),
            api_key=os.environ.get("LOCAL_LLM_API_KEY", "not-needed"),
        )
        model = requested_model or os.environ.get("LOCAL_LLM_MODEL") or "local"
    elif provider == "openai":
        client = OpenAI(api_key=_required_env("OPENAI_API_KEY"))
        model = requested_model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    elif provider == "openrouter":
        headers = {}
        if referer := os.environ.get("OPENROUTER_HTTP_REFERER"):
            headers["HTTP-Referer"] = referer
        if title := os.environ.get("OPENROUTER_APP_TITLE"):
            headers["X-Title"] = title
        client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=_required_env("OPENROUTER_API_KEY"),
            default_headers=headers or None,
        )
        model = requested_model or os.environ.get("OPENROUTER_MODEL")
        if not model:
            raise ValueError("OPENROUTER_MODEL is not configured and no model was requested.")
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    return client, model
