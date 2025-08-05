import uuid
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

# Blueprint-Name sollte 'workflows' sein, nicht nodes_bp
workflows_bp = Blueprint('workflows', __name__, url_prefix='/api/vaults/<int:vault_id>/workflows')

@workflows_bp.route('/', methods=['POST'], strict_slashes=False)
@jwt_required()
def start_fake_workflow(vault_id):  # vault_id Parameter hinzufügen
    task_id = str(uuid.uuid4())
    return jsonify({"task_id": task_id, "status": "running", "vault_id": vault_id})

@workflows_bp.route('/<task_id>/status', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_workflow_status(vault_id, task_id):  # beide Parameter
    # Mock mit zeitbasierter Progress-Simulation
    import time
    start_time = time.time()
    progress = min(100, int((start_time % 10) * 10))  # 0-100 über 10 Sekunden
    status = "complete" if progress >= 100 else "running"
    return jsonify({"task_id": task_id, "progress": progress, "status": status})