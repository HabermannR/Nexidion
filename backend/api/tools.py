import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

# Importiere die Services
from backend.services import chat_service

# Der Blueprint enthält die vault_id als dynamischen Teil des Präfixes.
# Alle Routen sind relativ zu diesem Prefix.
tools_bp = Blueprint('tools', __name__, url_prefix='/api/vaults/<int:vault_id>/tools')


@tools_bp.route('/<string:node_id>/propose-update', methods=['POST'], strict_slashes=False)
@jwt_required()
def propose_node_update(vault_id: int, node_id: str):
    """
    Generiert einen Update-Vorschlag für einen Node basierend auf optionalem Kontext.
    """
    user_id = int(get_jwt_identity())
    data = request.get_json()

    # KORREKTUR 1: Der Default-Wert für .get() ist bereits None. Das ist, was wir wollen.
    session_id = data.get('session_id')

    context_node_ids = data.get('context_node_ids', [])
    model = data.get('model')
    if not model:
        return jsonify({"error": "A 'model' is required in the request body."}), 400

    try:
        # KORREKTUR 2: Wir übergeben den vault_id aus der URL an den Service.
        # Dies ist die entscheidende Änderung.
        proposal = chat_service.propose_node_update(
            vault_id=vault_id,
            target_node_id=node_id,
            user_id=user_id,
            model=model,
            session_id=session_id,  # Kann jetzt None sein
            context_node_ids=context_node_ids
        )
        return jsonify(proposal)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        logging.error(f"Error in propose_node_update for node {node_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred while generating the proposal."}), 500
