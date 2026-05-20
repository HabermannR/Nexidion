import os
import sys
import tempfile
import threading
import subprocess
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.extensions import limiter
from backend.models import db, User
# Import the existing services and exceptions
from backend.services.vault_service import get_vault_access, assert_write_allowed
from backend.exceptions import DemoLockError, InsufficientVaultRoleError

# Create a new Blueprint for ingestion tasks
ingest_bp = Blueprint('ingest', __name__, url_prefix='/api/vaults/<int:vault_id>/ingest')


@ingest_bp.route('/pdf', methods=['POST'], strict_slashes=False)
@jwt_required()
@limiter.limit("5 per minute; 20 per hour")
def api_ingest_pdf(vault_id: int):
    """
    Takes a multipart/form-data PDF upload, saves it temporarily, and triggers
    the ingest_pdf.py pipeline via a background subprocess.
    """
    user_id = int(get_jwt_identity())

    # 1. Verify Write Access (Using the same pattern as your write endpoints)
    try:
        vault, role = get_vault_access(vault_id, user_id)
        user = db.session.get(User, user_id)
        assert_write_allowed(role, user)
    except DemoLockError as e:
        return jsonify({"error": str(e)}), 423
    except (PermissionError, InsufficientVaultRoleError) as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        logging.error(f"Error checking vault access during ingestion: {e}")
        return jsonify({"error": "An unexpected error occurred."}), 500

    # 2. Extract and Validate the File
    if 'file' not in request.files:
        return jsonify({"error": "No file provided in 'file' field."}), 400

    file = request.files['file']
    if file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "A valid .pdf file is required."}), 400

    # Optional parent node UUID
    parent_id = request.form.get('parent_id', '')

    # 3. Save File to a Secure Temporary Path
    # (We use mkstemp so we can safely pass the path to the subprocess)
    fd, temp_path = tempfile.mkstemp(suffix=".pdf", prefix="ingest_")
    with os.fdopen(fd, 'wb') as f:
        file.save(f)

    # 4. Define the Background Task
    # Running this in a thread/subprocess ensures the HTTP request doesn't timeout
    # while waiting for the LLM pipeline and Vision extraction to finish.
    def run_ingestion():
        try:
            # Run as a module (-m) from the project root so Python builds sys.path
            # correctly and `from backend.xxx import ...` works inside ingest_pdf.py.
            project_root = "/app"
            cmd = [
                sys.executable, "-m", "backend.services.ingest_pdf",
                temp_path, "--vault", str(vault_id)
            ]
            if parent_id:
                cmd.extend(["--parent", parent_id])

            # Inherit the current environment (already has PYTHONPATH, secrets, etc.)
            # and ensure project root is present in PYTHONPATH as a safety net.
            custom_env = os.environ.copy()
            python_path = custom_env.get("PYTHONPATH", "")
            if project_root not in python_path.split(":"):
                custom_env["PYTHONPATH"] = f"{project_root}:{python_path}" if python_path else project_root

            logging.info(f"Starting background PDF ingestion: {' '.join(cmd)}")

            # cwd=project_root makes relative imports and file lookups consistent
            subprocess.run(cmd, env=custom_env, cwd=project_root, check=True)

            logging.info(f"PDF ingestion completed successfully for vault {vault_id}")

        except subprocess.CalledProcessError as e:
            logging.error(f"PDF ingestion subprocess failed with exit code {e.returncode}")
        except Exception as e:
            logging.error(f"Error starting PDF ingestion subprocess: {e}", exc_info=True)
        finally:
            # Cleanup: Always delete the temporary PDF from the server disk
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    # 5. Start the Background Thread
    thread = threading.Thread(target=run_ingestion)
    thread.daemon = True
    thread.start()

    # 6. Immediately Respond with 202 Accepted
    return jsonify({
        "message": "PDF ingestion started. This may take a few minutes. Documents will appear in the vault automatically."
    }), 202