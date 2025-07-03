# app.py
import os
import json
import logging
import shutil
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
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
#npm run build

#todo
#multi vault
#async für Update, stream für chat
#scroll chat history
#Print kaputt
#diff view für versionen
#update node geht nicht vom handy
#Die Möglichkeit, einer Chat-Session einen besseren Titel zu geben (vielleicht vom LLM generiert).
#Ne: Anzeigen, welcher Kontext für welche Nachricht verwendet wurde, direkt in der UI.

def create_app(config_class=Config):
    """
    Erstellt und konfiguriert die Flask-App mithilfe des Application Factory-Musters.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- START: ENVIRONMENT-SPECIFIC CONFIGURATION ---

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
        # We need CORS to allow requests from the React dev server (e.g., http://localhost:5173)
        # to the Flask server (e.g., http://localhost:5001).
        CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

    # --- END: ENVIRONMENT-SPECIFIC CONFIGURATION ---

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SECURE_IMAGE_FOLDER = os.path.join(BASE_DIR, '..', 'secure_images')
    # Konfiguration aus der config.py-Datei laden
    app.config.from_object(config_class)

    # Überprüfen, ob die notwendigen Konfigurationen vorhanden sind
    if not all([app.config['JWT_SECRET_KEY'], app.config['ADMIN_USERNAME'], app.config['ADMIN_PASSWORD_HASH']]):
        raise ValueError("JWT_SECRET_KEY, ADMIN_USERNAME, and ADMIN_PASSWORD_HASH must be set in the .env file.")

    # Erweiterungen initialisieren
    db.init_app(app)
    migrate.init_app(app, db)
    jwt = JWTManager(app) # JWT initialisieren

    # --- API-Routen  ---

    @app.route('/api/login', methods=['POST'])
    def login():
        username = request.json.get('username', None)
        password = request.json.get('password', None)
        if (username == app.config['ADMIN_USERNAME'] and
                password and check_password_hash(app.config['ADMIN_PASSWORD_HASH'], password)):
            access_token = create_access_token(identity=username)
            return jsonify(access_token=access_token)
        return jsonify({"msg": "Bad username or password"}), 401

    @app.route('/api/nodes/tree', methods=['GET'])
    @jwt_required()
    def get_nodes_tree():
        tree = database.get_all_nodes_as_tree()
        return jsonify(tree)

    @app.route('/api/nodes/<node_id>', methods=['GET'])
    @jwt_required()
    def get_node(node_id):
        node = database.get_node_by_id(node_id)
        if node is None:
            return jsonify({"error": "Node not found"}), 404
        return jsonify(node)

    @app.route('/api/nodes', methods=['GET'])
    @jwt_required()
    def get_nodes_by_title_or_all():
        title_to_find = request.args.get('title')
        if title_to_find:
            nodes = database.get_nodes_by_title(title_to_find)
        else:
            nodes = database.get_all_nodes_as_list()
        return jsonify(nodes)

    @app.route('/api/nodes', methods=['POST'])
    @jwt_required()
    def create_node():
        data = request.json
        title = data.get('title')
        if not title:
            return jsonify({"error": "Title is required"}), 400
        new_node = database.create_node(
            title=title,
            content=data.get('content', ''),
            parent_id=data.get('parent_id')
        )
        return jsonify(new_node), 201

    @app.route('/api/nodes/<string:node_id>', methods=['PUT'])
    @jwt_required()
    def update_node(node_id):
        data = request.json

        if not data:
            return jsonify({"error": "Request body cannot be empty"}), 400

        update_fields = {}
        if 'title' in data:
            update_fields['title'] = data['title']
        if 'content' in data:
            update_fields['content'] = data['content']

        if not update_fields:
            return jsonify({"error": "No valid fields (title, content) provided for update"}), 400

        try:
            # Ruft die korrigierte DB-Funktion auf
            updated_node_obj = database.update_node(node_id, **update_fields)

            # KORREKTUR: Rufen Sie .to_dict() auf dem zurückgegebenen Objekt auf
            if not updated_node_obj:
                # Dieser Fall sollte durch die Korrektur in database.py nicht mehr eintreten
                raise Exception("Database function returned None unexpectedly.")

            return jsonify(updated_node_obj.to_dict())

        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            import traceback
            logging.error(f"Error updating node {node_id}: {traceback.format_exc()}")
            return jsonify({"error": "An internal server error occurred"}), 500

    @app.route('/api/nodes/<node_id>/rename', methods=['PATCH'])
    @jwt_required()
    def rename_node(node_id):
        """
        Renames a node. Expects a JSON body with a 'title' key.
        This is a more specific and lightweight operation than updating the whole node.
        """
        data = request.get_json()
        new_title = data.get('title')

        # Validate that the new title is provided and not just whitespace
        if not new_title or not new_title.strip():
            return jsonify({"error": "New title cannot be empty"}), 400

        try:
            updated_node = database.rename_node(node_id, new_title.strip())
            return jsonify(updated_node)
        except ValueError as e:
            # This will catch errors like "Node not found" from the database layer
            return jsonify({"error": str(e)}), 404
        except AttributeError:
            # This will catch the error if database.rename_node doesn't exist yet
            logging.error("database.rename_node function is not implemented.")
            return jsonify({"error": "Server-side function not implemented."}), 501

    @app.route('/api/nodes/<node_id>', methods=['DELETE'])
    @jwt_required()
    def delete_node_endpoint(node_id):
        try:
            database.delete_node(node_id)
            return jsonify({"message": "Node deleted successfully"}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/nodes/move', methods=['POST'])
    @jwt_required()
    def move_node():
        data = request.json
        try:
            database.move_node(data.get('node_id'), data.get('new_parent_id'))
            return jsonify({"message": "Node moved successfully"})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/nodes/content', methods=['POST'])
    @jwt_required()
    def get_nodes_content():
        data = request.get_json()
        node_ids = data.get('node_ids', [])
        nodes_data = database.get_context_from_ids(node_ids, with_titles=True)
        return jsonify({"content": nodes_data['context'], "titles": nodes_data['titles']})

    @app.route('/api/chat/sessions', methods=['GET'])
    @jwt_required()
    def list_chat_sessions():
        """Listet alle vergangenen Chat-Sitzungen auf."""
        sessions = chatservice.list_sessions()
        return jsonify(sessions)

    @app.route('/api/chat/sessions/<string:session_id>', methods=['GET'])
    @jwt_required()
    def get_chat_session_history(session_id):
        """Lädt den kompletten Verlauf einer spezifischen Chat-Sitzung."""
        session_history = chatservice.get_session_history(session_id)
        if session_history is None:
            return jsonify({"error": "Session not found"}), 404
        return jsonify(session_history)

    @app.route('/api/chat/sessions', methods=['POST'])
    @jwt_required()
    def create_chat_session():
        """Startet eine komplett neue Chat-Sitzung."""
        data = request.get_json()
        user_input = data.get('user_input')
        if not user_input:
            return jsonify({"error": "User input is required"}), 400

        try:
            response_data = chatservice.create_new_chat_session(
                user_input=user_input,
                node_ids=data.get('node_ids', []),
                model=data.get('model', 'claude-3-sonnet-20240229')
            )
            return jsonify(response_data), 201
        except Exception as e:
            logging.error(f"API Error creating chat session: {e}")
            return jsonify({"error": "Failed to create new chat session."}), 500

    @app.route('/api/chat/sessions/<string:session_id>/messages', methods=['POST'])
    @jwt_required()
    def add_message_to_session(session_id):
        """Fügt eine neue Nachricht zu einer BESTEHENDEN Chat-Sitzung hinzu."""
        data = request.get_json()
        user_input = data.get('user_input')
        if not user_input:
            return jsonify({"error": "User input is required"}), 400

        try:
            response_data = chatservice.add_message_to_session(
                session_id=session_id,
                user_input=user_input,
                node_ids=data.get('node_ids', [])
            )
            return jsonify(response_data)
        except ValueError as e:  # Fängt "Session not found" vom Service ab
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            logging.error(f"API Error adding message to session {session_id}: {e}")
            return jsonify({"error": "Failed to process message."}), 500

    @app.route('/api/nodes/<string:node_id>/propose-update', methods=['POST'])
    @jwt_required()
    def propose_node_update(node_id):
        """
        Generiert einen Aktualisierungsvorschlag für einen Node basierend auf dem
        Chatverlauf und dem Kontext.
        """
        data = request.json
        chat_history = data.get('chat_history')
        context_node_ids = data.get('context_node_ids')

        if chat_history is None or context_node_ids is None:
            return jsonify({"error": "Chat history and context node IDs are required"}), 400

        try:
            # Rufe die neue Service-Funktion auf
            proposal_data = chatservice.propose_node_update_from_chat(
                target_node_id=node_id,
                chat_history=chat_history,
                context_node_ids=context_node_ids,
                model=data.get('model', 'gemini-2.5-pro')
            )
            return jsonify(proposal_data)

        except ValueError as e:
            # Fängt Fehler wie "Node nicht gefunden" oder "AI gab ungültiges JSON zurück"
            return jsonify({"error": str(e)}), 400  # oder 500, je nach Fehlerart
        except Exception as e:
            # Fängt alle anderen Fehler, z.B. von der LLM-API
            logging.error(f"Failed to generate update proposal for node {node_id}: {e}")
            return jsonify({"error": "An internal error occurred while generating the proposal."}), 500

    @app.route('/api/image/<path:filename>')
    @jwt_required()  # SICHERHEIT: Nur eingeloggte Benutzer dürfen hier zugreifen
    def serve_secure_image(filename):
        """
        Liefert ein Bild aus dem sicheren Ordner aus.
        Der Zugriff ist nur mit einem gültigen JWT-Token möglich.
        `send_from_directory` ist sicher gegen Directory-Traversal-Angriffe.
        """
        try:
            # send_from_directory kümmert sich um das Senden der Datei mit dem richtigen MIME-Typ
            return send_from_directory(SECURE_IMAGE_FOLDER, filename)
        except FileNotFoundError:
            return jsonify({"error": "Image not found"}), 404


    # --- Frontend Serving (Catch-all route) ---
    # This route is only effective in PRODUCTION mode when the static_folder is set.
    # It ensures that any request not matching an API route is served the React app.
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        # Wir brauchen einen expliziten Pfad zum Build-Verzeichnis
        # Da static_folder nicht mehr in app.config ist.
        frontend_dir = os.path.join(BASE_DIR, '..', 'frontend', 'dist')

        if path != "" and os.path.exists(os.path.join(frontend_dir, path)):
            return send_from_directory(frontend_dir, path)
        else:
            return send_from_directory(frontend_dir, 'index.html')

    @app.cli.command('init-db')
    @click.option('--root-title', default='Summary', help='The title for the root node of the knowledge base.')
    def init_db_command(root_title):
        """
        Creates the database tables and the initial root node.
        Example: flask init-db --root-title "My Project Wiki"
        """
        try:
            database.init_db(root_node_title=root_title)
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
    @click.option('--out', default='knowledge_base_export.json', help='Output JSON file name.')
    def export_json_command(out):
        """
        Exports the entire knowledge base (nodes and versions) to a JSON file.
        Useful for data portability and inspection, not for primary backup.
        """
        print("Gathering all nodes and versions for export...")
        # We need a special function that gets EVERYTHING for the export
        # You would need to add this function to your database.py
        try:
            full_tree = database.get_full_tree_for_export()

            with open(out, 'w', encoding='utf-8') as f:
                json.dump(full_tree, f, indent=2, ensure_ascii=False)

            print("-----------------------------------------")
            print(f"✅ Knowledge base exported successfully to: {out}")
            print("-----------------------------------------")
        except Exception as e:
            print(f"🔥 An error occurred during JSON export: {e}")

    return app



# --- App Ausführung (For local development ONLY) ---
# This block is NOT run on PythonAnywhere.
if __name__ == '__main__':
    # We call create_app() which will automatically run in 'development' mode
    # because the APP_ENV variable is not set.
    app = create_app()
    app.run(host='0.0.0.0', port=5001, debug=True)