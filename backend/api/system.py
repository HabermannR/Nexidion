import os
from flask import Blueprint, jsonify, current_app

system_bp = Blueprint('system', __name__, url_prefix='/api/system')

@system_bp.route('/config', methods=['GET'])
def get_config():
    payload = {
        "summary_providers": {
            "local": {"configured": bool(os.environ.get("LOCAL_LLM_URL")), "external": False},
            "openai": {"configured": bool(os.environ.get("OPENAI_API_KEY")), "external": True},
        },
        "default_summary_provider": os.environ.get("SUMMARY_PROVIDER", "local"),
        "default_visual_mode": os.environ.get("SUMMARY_VISUAL_MODE", "off"),
    }

    return jsonify(payload), 200
