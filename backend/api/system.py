import os
from flask import Blueprint, jsonify, current_app
from backend.services.openrouter_catalog import get_curated_models

system_bp = Blueprint('system', __name__, url_prefix='/api/system')

OPENAI_MODELS = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")

@system_bp.route('/config', methods=['GET'])
def get_config():
    configured_openai_model = os.environ.get("OPENAI_MODEL")
    openai_default = (configured_openai_model
                      if configured_openai_model in OPENAI_MODELS
                      else OPENAI_MODELS[0])
    providers = {
        "local": {"configured": bool(os.environ.get("LOCAL_LLM_URL")), "external": False,
                  "default_model": os.environ.get("LOCAL_LLM_MODEL")},
        "openai": {"configured": bool(os.environ.get("OPENAI_API_KEY")), "external": True,
                   "default_model": openai_default, "models": list(OPENAI_MODELS)},
        "openrouter": {
            "configured": bool(os.environ.get("OPENROUTER_API_KEY")),
            "external": True,
            "default_model": os.environ.get("OPENROUTER_MODEL"),
            "supports_custom_model": True,
        },
    }
    payload = {
        "summary_providers": providers,
        "task_providers": providers,
        "default_summary_provider": os.environ.get("SUMMARY_PROVIDER", "local"),
        "default_visual_mode": os.environ.get("SUMMARY_VISUAL_MODE", "off"),
    }

    return jsonify(payload), 200


@system_bp.route('/openrouter-models', methods=['GET'])
def get_openrouter_models():
    """Expose curated public model metadata, never OpenRouter credentials."""
    return jsonify({"models": get_curated_models()}), 200
