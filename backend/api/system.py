from flask import Blueprint, jsonify, current_app

system_bp = Blueprint('system', __name__, url_prefix='/api/system')

@system_bp.route('/config', methods=['GET'])
def get_config():
    return jsonify({"demo_mode_enabled": current_app.config["DEMO_MODE_ENABLED"]}), 200