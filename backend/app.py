# app.py
import os
import json
import logging
import shutil
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, JWTManager
from flask_migrate import Migrate
import click

# Load environment variables from .env file, especially for local development
load_dotenv()

from config import Config
from models import db
import chatservice
import database

migrate = Migrate()

#To Run Locally:
#Terminal 1 (Backend): Navigate to your backend folder and run python app.py.
#Terminal 2 (Frontend): Navigate to your frontend folder and run npm start (or npm run dev).
#npm run dev -- --host
#npm run build
#git status --ignored

#todo
#async für Update
#Konzept: Sie erstellen einen AbortController vor dem fetch, übergeben sein signal an die fetch-Optionen und rufen .abort() in einem useEffect-Cleanup auf, wenn die Komponente verlassen wird oder ein neuer Request startet. Das ist fortgeschritten, aber ein riesiger Gewinn für die Stabilität.
#UI-Verbesserung für Streaming
#Anstatt den Text einfach nur erscheinen zu lassen, könnten Sie einen kleinen blinkenden Cursor (wie bei einer Schreibmaschine) am Ende der Assistant-Antwort anzeigen, solange der Stream aktiv ist. Das macht visuell sofort klar, dass die Antwort noch nicht fertig ist.
#update node geht nicht vom handy, jetzt anderer Fehler!
#local structured
#bubble up? pro parent die childs nehmen um den parent zu verbessern und dann hoch bubblen
#unlock knowledge base
#rebrand?
#special page automatisieren
#Die Möglichkeit, einer Chat-Session einen besseren Titel zu geben (vielleicht vom LLM generiert).

def create_app(config_class=Config):
    """Application Factory Pattern"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Detect the environment. We'll set APP_ENV to 'production' on PythonAnywhere.
    # If it's not set, we default to 'development'.
    APP_ENV = os.getenv('APP_ENV', 'development')

    if APP_ENV == 'production':
        # PRODUCTION MODE (PythonAnywhere)
        # In production, Flask serves the static React files.
        # The path '../frontend/dist' assumes your 'backend' and 'frontend' folders are siblings.
        # 'dist' is the default build folder for Vite. If you use Create React App, change it to 'build'.
        print("----> Running in PRODUCTION mode")
        #app = Flask(__name__, static_folder='../frontend/dist', static_url_path='')
        app = Flask(__name__)
        # CORS is not needed in production because the API and frontend are served from the same domain.

    else:
        # DEVELOPMENT MODE (Your Local PC)
        # In development, Flask ONLY acts as an API. The React dev server serves the frontend.
        print("----> Running in DEVELOPMENT mode")
        app = Flask(__name__)

        # Get your PC's local IP address (replace with your actual IP)
        local_ip = "192.168.2.59"

        # We need CORS to allow requests from the React dev server on your PC and your phone.
        allowed_origins = [
            "http://localhost:5173",  # For local development on your PC
            f"http://{local_ip}:5173"  # For accessing from your phone
        ]
        CORS(app, resources={r"/api/*": {"origins": allowed_origins}})
        
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SECURE_IMAGE_FOLDER = os.path.join(BASE_DIR, '..', 'secure_images')
    app.config.from_object(config_class)

    if not all([app.config['JWT_SECRET_KEY'], app.config['ADMIN_USERNAME'], app.config['ADMIN_PASSWORD_HASH']]):
        raise ValueError("JWT_SECRET_KEY, ADMIN_USERNAME, and ADMIN_PASSWORD_HASH must be set.")

    db.init_app(app)
    migrate.init_app(app, db)
    JWTManager(app)

    # ==============================================================================
    # HELPER FUNCTIONS
    # ==============================================================================

    def _get_vault_id_from_request():
        """
        Helper to get and validate vault_id from request query arguments for GET requests.
        Raises ValueError if not found or invalid.
        """
        vault_id = request.args.get('vault_id', type=int)
        if not vault_id:
            raise ValueError("A 'vault_id' query parameter is required and must be an integer.")
        return vault_id

    # ==============================================================================
    # AUTHENTICATION API
    # ==============================================================================

    @app.route('/api/login', methods=['POST'])
    def login():
        username = request.json.get('username', None)
        password = request.json.get('password', None)
        if username == app.config['ADMIN_USERNAME'] and check_password_hash(app.config['ADMIN_PASSWORD_HASH'],
                                                                            password):
            access_token = create_access_token(identity=username)
            return jsonify(access_token=access_token)
        return jsonify({"msg": "Bad username or password"}), 401

    # ==============================================================================
    # VAULT API
    # ==============================================================================

    @app.route('/api/vaults', methods=['GET'])
    @jwt_required()
    def list_vaults():
        vaults = database.get_all_vaults()
        return jsonify([v.to_dict() for v in vaults])

    @app.route('/api/vaults', methods=['POST'])
    @jwt_required()
    def create_vault():
        vault_name = request.json.get('name')
        if not vault_name:
            return jsonify({"error": "Vault name is required"}), 400
        try:
            new_vault = database.create_vault_with_root_node(name=vault_name)
            return jsonify(new_vault.to_dict()), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 409  # Conflict

    @app.route('/api/vaults/<int:vault_id>', methods=['PUT'])
    @jwt_required()
    def rename_vault(vault_id):
        new_name = request.json.get('name')
        if not new_name:
            return jsonify({"error": "New name is required"}), 400
        try:
            updated_vault = database.rename_vault(vault_id, new_name)
            return jsonify(updated_vault.to_dict())
        except ValueError as e:
            return jsonify({"error": str(e)}), 409

    @app.route('/api/vaults/<int:vault_id>', methods=['DELETE'])
    @jwt_required()
    def delete_vault(vault_id):
        try:
            database.delete_vault(vault_id)
            return jsonify({"message": f"Vault with ID {vault_id} deleted."}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    # ==============================================================================
    # NODE API
    # ==============================================================================

    @app.route('/api/nodes/tree', methods=['GET'])
    @jwt_required()
    def get_nodes_tree():
        try:
            vault_id = _get_vault_id_from_request()
            tree = database.get_all_nodes_as_tree(vault_id=vault_id)
            return jsonify(tree)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/nodes/details', methods=['GET'])
    @jwt_required()
    def get_nodes_details():
        """
        Fetches a list of full node objects (including content) for a given list of IDs.
        This is specifically for features like the print preview.
        """
        try:
            vault_id = _get_vault_id_from_request()
            node_ids = request.args.getlist('node_ids', type=str)
            if not node_ids:
                return jsonify([])  # Gib einfach eine leere Liste zurück, kein Fehler

            # Wir brauchen eine neue Datenbankfunktion dafür (siehe Schritt 2)
            nodes = database.get_nodes_by_ids(node_ids=node_ids, vault_id=vault_id)
            return jsonify(nodes)

        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/nodes/content', methods=['GET'])
    @jwt_required()
    def get_nodes_content():
        """
        **THIS IS THE FIX FOR THE ORIGINAL PROBLEM**
        Fetches the concatenated content and titles for a list of node IDs.
        """
        try:
            vault_id = _get_vault_id_from_request()
            node_ids = request.args.getlist('node_ids', type=str)
            if not node_ids:
                return jsonify({"error": "node_ids query parameter is required"}), 400

            result = database.get_content_for_nodes(node_ids=node_ids, vault_id=vault_id)
            return jsonify(result)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/nodes/<string:node_id>', methods=['GET'])
    @jwt_required()
    def get_node(node_id):
        try:
            vault_id = _get_vault_id_from_request()
            node = database.get_node_by_id(node_id, vault_id=vault_id)
            if node is None:
                return jsonify({"error": "Node not found in the specified vault"}), 404
            return jsonify(node)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/nodes', methods=['POST'])
    @jwt_required()
    def create_node():
        data = request.json
        vault_id = data.get('vault_id')
        title = data.get('title')
        if not vault_id or not title:
            return jsonify({"error": "vault_id and title are required"}), 400
        try:
            new_node = database.create_node(
                title=title,
                content=data.get('content', ''),
                parent_id=data.get('parent_id'),
                vault_id=vault_id
            )
            # We call get_node_by_id to get the full dict representation
            return jsonify(database.get_node_by_id(new_node.id, vault_id)), 201
        except Exception as e:
            logging.error(f"Error creating node: {e}")
            return jsonify({"error": "An internal server error occurred"}), 500

    @app.route('/api/nodes/<string:node_id>', methods=['PUT'])
    @jwt_required()
    def update_node(node_id):
        data = request.json
        vault_id = data.get('vault_id')
        if not vault_id:
            return jsonify({"error": "vault_id is required"}), 400
        try:
            # DIESE EINE ZEILE LÖST DAS PROBLEM AN DER QUELLE
            data.pop('vault_id', None)

            updated_node = database.update_node(node_id, vault_id, **data)
            return jsonify(updated_node.to_dict(include_content=True))
        except ValueError as e:
            return jsonify({"error": str(e)}), 404

    @app.route('/api/nodes/<string:node_id>', methods=['DELETE'])
    @jwt_required()
    def delete_node_endpoint(node_id):
        try:
            vault_id = _get_vault_id_from_request()
            database.delete_node(node_id, vault_id=vault_id)
            return jsonify({"message": "Node deleted successfully"}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/nodes/move', methods=['POST'])
    @jwt_required()
    def move_node():
        data = request.json
        vault_id = data.get('vault_id')
        node_id = data.get('node_id')
        new_parent_id = data.get('new_parent_id')
        if not vault_id or not node_id:
            return jsonify({"error": "vault_id and node_id are required"}), 400
        try:
            database.move_node(node_id, new_parent_id, vault_id=vault_id)
            return jsonify({"message": "Node moved successfully"})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/nodes/<string:node_id>/propose-update', methods=['POST'])
    @jwt_required()
    def propose_node_update(node_id):
        data = request.json
        vault_id = data.get('vault_id')
        if not vault_id:
            return jsonify({"error": "vault_id is required"}), 400
        try:
            proposal = chatservice.propose_node_update_from_chat(
                target_node_id=node_id,
                chat_history=data.get('chat_history', []),
                context_node_ids=data.get('context_node_ids', []),
                model=data.get('model', 'gemini-2.5-pro'),
                vault_id=vault_id
            )
            return jsonify(proposal)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/nodes/<node_id>/rename', methods=['PATCH'])
    @jwt_required()
    def rename_node(node_id):
        """
        Renames a node. Expects a JSON body with a 'title' key and 'vault_id' key.
        """
        data = request.get_json()
        new_title = data.get('title')
        vault_id = data.get('vault_id')  # Add this line

        # Validate that the new title is provided and not just whitespace
        if not new_title or not new_title.strip():
            return jsonify({"error": "New title cannot be empty"}), 400

        # Validate vault_id
        if not vault_id:
            return jsonify({"error": "vault_id is required"}), 400

        try:
            # Pass vault_id to your database function
            updated_node = database.rename_node(node_id, new_title.strip(), vault_id=vault_id)
            return jsonify(updated_node)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except AttributeError:
            logging.error("database.rename_node function is not implemented.")
            return jsonify({"error": "Server-side function not implemented."}), 501

    # ==============================================================================
    # CHAT API
    # ==============================================================================

    # --- NON-STREAMING CHAT ENDPOINTS (Existing) ---

    @app.route('/api/chat/sessions', methods=['GET'])
    @jwt_required()
    def list_chat_sessions():
        try:
            vault_id = _get_vault_id_from_request()
            sessions = chatservice.list_sessions(vault_id=vault_id)
            return jsonify(sessions)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/chat/sessions/<string:session_id>', methods=['GET'])
    @jwt_required()
    def get_chat_session_history(session_id):
        history = chatservice.get_session_history(session_id)
        if history is None:
            return jsonify({"error": "Session not found"}), 404
        return jsonify(history)

    @app.route('/api/chat/sessions/<string:session_id>', methods=['DELETE'])
    @jwt_required()
    def delete_chat_session(session_id):
        """Deletes a chat session and all of its associated messages."""
        try:
            database.delete_chat_session(session_id)
            return jsonify({"message": f"Session with ID {session_id} deleted successfully."}), 200
        except ValueError as e:
            # This error is raised by the database function if the session is not found
            return jsonify({"error": str(e)}), 404

    @app.route('/api/chat/sessions', methods=['POST'])
    @jwt_required()
    def create_chat_session():
        # This endpoint is kept for non-streaming clients or backup use
        data = request.json
        vault_id = data.get('vault_id')
        user_input = data.get('user_input')
        if not vault_id or not user_input:
            return jsonify({"error": "vault_id and user_input are required"}), 400
        try:
            response = chatservice.create_new_chat_session(
                user_input=user_input,
                node_ids=data.get('node_ids', []),
                model=data.get('model', 'claude-3-sonnet-20240229'),
                vault_id=vault_id
            )
            return jsonify(response), 201
        except Exception as e:
            logging.error(f"Error in create_chat_session: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/chat/sessions/<string:session_id>/messages', methods=['POST'])
    @jwt_required()
    def add_message_to_session(session_id):
        # This endpoint is kept for non-streaming clients or backup use
        data = request.json
        user_input = data.get('user_input')
        if not user_input:
            return jsonify({"error": "user_input is required"}), 400
        try:
            response = chatservice.add_message_to_session(
                session_id=session_id,
                user_input=user_input,
                node_ids=data.get('node_ids', [])
            )
            return jsonify(response)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            logging.error(f"Error in add_message_to_session for session {session_id}: {e}")
            return jsonify({"error": str(e)}), 500

    # --- STREAMING CHAT ENDPOINTS (NEW) ---

    @app.route('/api/chat/sessions/stream', methods=['POST'])
    @jwt_required()
    def stream_new_chat_session():
        """Creates a new chat session and streams the response within an app context."""
        data = request.json
        vault_id = data.get('vault_id')
        user_input = data.get('user_input')
        if not vault_id or not user_input:
            return jsonify({"error": "vault_id and user_input are required"}), 400

        # We create the generator first, but DON'T execute it yet.
        generator = chatservice.stream_new_chat_session(
            user_input=user_input,
            node_ids=data.get('node_ids', []),
            model=data.get('model', 'claude-3-sonnet-20240229'),
            vault_id=vault_id
        )

        # THIS IS THE FIX: A wrapper generator that keeps the context alive.
        def stream_with_context():
            with app.app_context():
                # yield from will pull from the original generator and pass it through
                yield from generator

        # We return a response from the NEW generator that has the context.
        return Response(stream_with_context(), mimetype='text/event-stream')

    @app.route('/api/chat/sessions/<string:session_id>/messages/stream', methods=['POST'])
    @jwt_required()
    def stream_message_to_session(session_id):
        """Adds a message to an existing session and streams the response within an app context."""
        data = request.json
        user_input = data.get('user_input')
        if not user_input:
            return jsonify({"error": "user_input is required"}), 400

        # Create the original generator
        generator = chatservice.stream_message_in_session(
            session_id=session_id,
            user_input=user_input,
            node_ids=data.get('node_ids', [])
        )

        # THE SAME FIX: Wrap it in a function that provides the app context
        def stream_with_context():
            with app.app_context():
                yield from generator

        return Response(stream_with_context(), mimetype='text/event-stream')


    # ==============================================================================
    # FILE SERVING & CLI
    # ==============================================================================

    @app.route('/api/image/<path:filename>')
    @jwt_required()
    def serve_secure_image(filename):
        try:
            return send_from_directory(SECURE_IMAGE_FOLDER, filename)
        except FileNotFoundError:
            return jsonify({"error": "Image not found"}), 404

    # Catch-all route for frontend serving in production
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        # API-Aufrufe sind bereits durch ihre spezifischen Routen abgedeckt.
        # Alles andere muss an das Frontend weitergeleitet werden.
        # PythonAnywhere's "Static Files" wird echte statische Dateien (CSS, JS) abfangen.
        # Diese Route fängt nur die "virtuellen" React-Router-Pfade ab.

        # Der Pfad zum Build-Verzeichnis des Frontends
        static_folder_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')

        # Prüfe, ob die angeforderte Ressource eine existierende Datei ist (z.B. `favicon.ico`)
        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)
        else:
            # Für alle anderen Pfade, liefere die Haupt-HTML-Datei der App aus
            return send_from_directory(static_folder_path, 'index.html')

    # CLI commands here...
    @app.cli.command('init-db')
    @click.option('--root-title', default='Summary', help='The title for the root node of the knowledge base.')
    def init_db_command(root_title):
        """
        Creates the database tables and the initial root node.
        Example: flask init-db --root-title "My Project Wiki"
        """
        try:
            database.init_db()
            print("-----------------------------------------")
            print("✅ Database initialized successfully!")
            print("-----------------------------------------")
        except Exception as e:
            print("-----------------------------------------")
            print(f"🔥 An error occurred during database initialization: {e}")
            print("-----------------------------------------")

    @app.cli.command('backup-db')
    @click.option('--out', default=None, help='Output file path. Defaults to a timestamped file in a "backups" folder.')
    def backup_db_command(out):
        """
        Creates a complete, timestamped backup of the SQLite database file.
        This is the recommended method for disaster recovery.
        """
        db_path = app.config['DATABASE_FILE_PATH']  # You'll need to add this to your config.py

        if not os.path.exists(db_path):
            print(f"🔥 Error: Database file not found at {db_path}")
            return

        if out is None:
            backup_dir = os.path.join(os.path.dirname(BASE_DIR), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            out = os.path.join(backup_dir, f'kb-backup-{timestamp}.sqlite')

        try:
            shutil.copy(db_path, out)
            print("-----------------------------------------")
            print(f"✅ Database backed up successfully to: {out}")
            print("-----------------------------------------")
        except Exception as e:
            print(f"🔥 An error occurred during backup: {e}")


    @app.cli.command('export-json')
    @click.option('--vault-id', type=int, help='The ID of the vault to export.')
    @click.option('--out', default=None, help='Output JSON file name. Defaults to vault_name.json.')
    def export_json_command(vault_id, out):
        """Exports a specific vault to a JSON file, including all its nodes and versions."""

        # Holen der App-Kontext, damit wir die Datenbank abfragen können
        from flask.cli import with_appcontext

        @with_appcontext
        def perform_export():
            # 1. Alle verfügbaren Vaults abrufen
            all_vaults = database.get_all_vaults()
            if not all_vaults:
                print("🔥 Error: No vaults found in the database.")
                return

            selected_vault = None
            if vault_id:
                # Wenn eine ID angegeben wurde, finde den Vault
                selected_vault = next((v for v in all_vaults if v.id == vault_id), None)
                if not selected_vault:
                    print(f"🔥 Error: Vault with ID {vault_id} not found.")
                    return
            else:
                # Wenn keine ID angegeben wurde, den Benutzer fragen
                print("Available vaults:")
                for i, vault in enumerate(all_vaults):
                    print(f"  [{i + 1}] ID: {vault.id}, Name: {vault.name}")

                try:
                    choice = int(input("Please enter the number of the vault to export: ")) - 1
                    if 0 <= choice < len(all_vaults):
                        selected_vault = all_vaults[choice]
                    else:
                        print("🔥 Invalid selection.")
                        return
                except ValueError:
                    print("🔥 Invalid input. Please enter a number.")
                    return

            # 2. Dateinamen festlegen, falls nicht angegeben
            if out is None:
                # Ersetze Leerzeichen und Sonderzeichen für einen sicheren Dateinamen
                safe_name = "".join(c for c in selected_vault.name if c.isalnum() or c in (' ', '_')).rstrip()
                out_filename = f"{safe_name.replace(' ', '_')}_export.json"
            else:
                out_filename = out

            # 3. Den eigentlichen Export durchführen
            print(f"Exporting vault '{selected_vault.name}' (ID: {selected_vault.id})...")
            try:
                full_tree = database.get_full_tree_for_export(vault_id=selected_vault.id)

                with open(out_filename, 'w', encoding='utf-8') as f:
                    json.dump(full_tree, f, indent=2, ensure_ascii=False)

                print("-----------------------------------------")
                print(f"✅ Vault exported successfully to: {out_filename}")
                print("-----------------------------------------")
            except Exception as e:
                print(f"🔥 An error occurred during JSON export: {e}")

        perform_export()

    return app



# --- App Ausführung (For local development ONLY) ---
# This block is NOT run on PythonAnywhere.
if __name__ == '__main__':
    # We call create_app() which will automatically run in 'development' mode
    # because the APP_ENV variable is not set.
    app = create_app()
    app.run(host='0.0.0.0', port=5001, debug=True)