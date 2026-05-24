from flask import Blueprint, jsonify, current_app

system_bp = Blueprint('system', __name__, url_prefix='/api/system')

@system_bp.route('/config', methods=['GET'])
def get_config():
    demo_enabled = current_app.config["DEMO_MODE_ENABLED"]
    payload = {"demo_mode_enabled": demo_enabled}

    if demo_enabled:
        # Expose the demo task instruction so the frontend can prefill it for guests.
        try:
            from agent.demo_script import DEMO_INSTRUCTION
            payload["demo_instruction"] = DEMO_INSTRUCTION
        except ImportError:
            pass

    return jsonify(payload), 200
