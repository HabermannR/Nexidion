# backend/api/llm.py

from flask import Blueprint, jsonify, current_app
from flask_jwt_extended import jwt_required

# Blueprint für LLM-bezogene Routen erstellen
llm_bp = Blueprint('llm', __name__, url_prefix='/api/llm')

@llm_bp.route('/models', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_available_models():
    """Stellt die Liste der verfügbaren LLM-Modelle aus der Konfiguration bereit."""
    try:
        # Greife auf die Konfiguration über den 'current_app'-Kontext zu
        models = current_app.config['AVAILABLE_LLM_MODELS']
        if not isinstance(models, list):
             return jsonify({"error": "Model configuration is invalid."}), 500
        return jsonify(models)
    except KeyError:
        # Falls der Konfigurationsschlüssel fehlt
        return jsonify({"error": "AVAILABLE_LLM_MODELS not found in configuration."}), 500
