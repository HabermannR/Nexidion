# app.py
import os
import json
import logging
import shutil
import uuid
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager
from flask_migrate import Migrate
import click

# Load environment variables from .env file, especially for local development
load_dotenv()

from backend.config import Config
from backend.models import db, User
import backend.chatservice as chatservice
import backend.database as database

#import time
#from flask import g

migrate = Migrate()


# To Run Locally:
# Terminal 1 (Backend): Navigate to your backend folder and run python app.py.
# Terminal 2 (Frontend): Navigate to your frontend folder and run npm start (or npm run dev).
# npm run dev -- --host
# npm run build
# git status --ignored

def create_app(config_class=Config):
    """Application Factory Pattern"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    APP_ENV = os.getenv('APP_ENV', 'development')

    if APP_ENV == 'production':
        print("----> Running in PRODUCTION mode")
        app = Flask(__name__)
    else:
        print("----> Running in DEVELOPMENT mode")
        app = Flask(__name__)
        local_ip = os.getenv("LOCAL_IP", "192.168.2.59")
        allowed_origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            f"http://{local_ip}:5173"
        ]
        CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SECURE_IMAGE_FOLDER = os.path.join(BASE_DIR, '..', 'secure_images')
    app.config.from_object(config_class)

    if not app.config['JWT_SECRET_KEY']:
        raise ValueError("JWT_SECRET_KEY must be set in your .env file.")

    db.init_app(app)
    migrate.init_app(app, db)
    JWTManager(app)

    #@app.before_request
    #def before_request_time():
    #    g.start_time = time.time()

    #@app.after_request
    #def after_request_time(response):
    #    if 'start_time' in g:
    #        duration = (time.time() - g.start_time) * 1000
    #        logging.info(f"Request an {request.path} mit {request.method} dauerte {duration:.2f}ms")
    #    return response

    # ==============================================================================
    # HELPER FUNCTIONS
    # ==============================================================================
    def _get_vault_id_from_request():
        # Zuerst aus den Query-Parametern versuchen
        vault_id_str = request.args.get('vault_id')

        # Wenn nicht in Query-Parametern, aus dem JSON-Body versuchen
        if not vault_id_str:
            if request.is_json and 'vault_id' in request.json:
                vault_id_str = request.json.get('vault_id')

        # Wenn wir immer noch nichts haben, Fehler werfen
        if not vault_id_str:
            raise ValueError("A 'vault_id' parameter is required (in query string or JSON body).")

        # Jetzt, wo wir einen String haben, versuchen wir ihn in einen int zu konvertieren
        try:
            return int(vault_id_str)
        except (ValueError, TypeError):
            # Fängt den Fall ab, dass jemand z.B. "abc" oder 'null' sendet
            raise ValueError(f"The 'vault_id' must be a valid integer, but got '{vault_id_str}'.")

    def is_valid_uuid(val):
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False

    # ==============================================================================
    # AUTHENTICATION API
    # ==============================================================================
    @app.route('/api/login', methods=['POST'])
    def login():
        username = request.json.get('username', None)
        password = request.json.get('password', None)

        if not username or not password:
            return jsonify({"msg": "Username and password are required"}), 400

        user = User.query.filter_by(username=username, user_type='human').first()
        if user and user.check_password(password):
            identity_as_string = str(user.id)
            access_token = create_access_token(identity=identity_as_string)
            return jsonify(access_token=access_token, user=user.to_dict())

        return jsonify({"msg": "Bad username or password"}), 401

    @app.route('/api/auth/me', methods=['GET'])
    @jwt_required()
    def get_current_user_profile():
        current_user_id = int(get_jwt_identity())
        user = User.query.get(current_user_id)
        if user:
            return jsonify(user=user.to_dict()), 200
        return jsonify({"msg": "User not found"}), 404

    # ==============================================================================
    # VAULT API
    # ==============================================================================
    @app.route('/api/vaults', methods=['GET'])
    @jwt_required()
    def list_vaults():
        current_user_id = int(get_jwt_identity())
        vaults = database.get_vaults_for_user(user_id=current_user_id)
        return jsonify([v.to_dict() for v in vaults])

    @app.route('/api/vaults', methods=['POST'])
    @jwt_required()
    def create_vault():
        current_user_id = int(get_jwt_identity())
        vault_name = request.json.get('name')
        if not vault_name:
            return jsonify({"error": "Vault name is required"}), 400
        try:
            # ## KORRIGIERT ##: owner_id wird jetzt übergeben
            new_vault = database.create_vault_with_root_node(name=vault_name, owner_id=current_user_id)
            return jsonify(new_vault.to_dict()), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 409

    @app.route('/api/vaults/<int:vault_id>', methods=['PUT'])
    @jwt_required()
    def rename_vault(vault_id):
        current_user_id = int(get_jwt_identity())
        new_name = request.json.get('name')
        if not new_name:
            return jsonify({"error": "New name is required"}), 400
        try:
            updated_vault = database.rename_vault(vault_id, new_name, user_id=current_user_id)
            return jsonify(updated_vault.to_dict())
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route('/api/vaults/<int:vault_id>', methods=['DELETE'])
    @jwt_required()
    def delete_vault(vault_id):
        current_user_id = int(get_jwt_identity())
        try:
            database.delete_vault(vault_id, user_id=current_user_id)
            return jsonify({"message": f"Vault with ID {vault_id} deleted."}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    # ==============================================================================
    # NODE API
    # ==============================================================================
    @app.route('/api/nodes/tree', methods=['GET'])
    @jwt_required()
    def get_nodes_tree():
        current_user_id = int(get_jwt_identity())
        try:
            vault_id = _get_vault_id_from_request()
            tree = database.get_all_nodes_as_tree(vault_id=vault_id, user_id=current_user_id)
            return jsonify(tree)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    ## WIEDERHERGESTELLT und für Multi-User angepasst ##
    @app.route('/api/nodes', methods=['GET'])
    @jwt_required()
    def get_nodes_by_title_or_all():
        current_user_id = int(get_jwt_identity())
        try:
            vault_id = _get_vault_id_from_request()
            title_to_find = request.args.get('title')

            # HINWEIS: Ihre alte API hat hier eine Liste zurückgegeben.
            # Die neue `database.py` hat `get_node_by_title`, das nur EIN Ergebnis liefert.
            # Wir behalten die Logik bei, die ein einzelnes, bestes Ergebnis liefert.
            # Wenn Sie eine Liste von Suchergebnissen benötigen, müsste eine neue DB-Funktion her.
            if title_to_find:
                node = database.get_node_by_title(title_to_find, vault_id=vault_id, user_id=current_user_id)
                return jsonify([node] if node else [])  # Gibt eine Liste mit einem oder keinem Element zurück
            else:
                # `get_all_nodes_as_list` wurde in der vorherigen Antwort korrigiert
                nodes = database.get_all_nodes_as_list(vault_id=vault_id, user_id=current_user_id)
                return jsonify(nodes)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route('/api/nodes/details', methods=['GET'])
    @jwt_required()
    def get_nodes_details():
        current_user_id = int(get_jwt_identity())
        try:
            vault_id = _get_vault_id_from_request()
            node_ids = request.args.getlist('node_ids', type=str)
            if not node_ids:
                return jsonify([])

            # MODIFIZIERT: Funktion braucht user_id zur Autorisierung
            nodes = database.get_nodes_by_ids(node_ids=node_ids, vault_id=vault_id, user_id=current_user_id)
            return jsonify(nodes)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except PermissionError as e:  # NEU
            return jsonify({"error": str(e)}), 403

    @app.route('/api/nodes/content', methods=['GET'])
    @jwt_required()
    def get_nodes_content():
        current_user_id = int(get_jwt_identity())
        try:
            vault_id = _get_vault_id_from_request()
            node_ids = request.args.getlist('node_ids', type=str)
            if not node_ids:
                return jsonify({"error": "node_ids query parameter is required"}), 400

            result = database.get_content_for_nodes(node_ids=node_ids, vault_id=vault_id, user_id=current_user_id)
            return jsonify(result)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    # ## KORRIGIERT ##: Dieser Endpunkt ist spezifischer als der alte `GET /api/nodes/<node_id>`
    @app.route('/api/nodes/<string:identifier>', methods=['GET'])
    @jwt_required()
    def get_node_by_identifier(identifier):
        current_user_id = int(get_jwt_identity())
        try:
            vault_id = _get_vault_id_from_request()
            node = None
            if is_valid_uuid(identifier):
                node = database.get_node_by_id(identifier, vault_id=vault_id, user_id=current_user_id)
            else:
                node = database.get_node_by_title(identifier, vault_id=vault_id, user_id=current_user_id)

            if node is None:
                return jsonify({"error": f"Node with identifier '{identifier}' not found in the specified vault"}), 404
            return jsonify(node)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route('/api/nodes', methods=['POST'])
    @jwt_required()
    def create_node():
        current_user_id = int(get_jwt_identity())
        data = request.json
        vault_id = data.get('vault_id')
        title = data.get('title')
        if not vault_id or not title:
            return jsonify({"error": "vault_id and title are required"}), 400
        try:
            # ## KORRIGIERT ##: `author_id` wird übergeben
            new_node = database.create_node(
                title=title,
                content=data.get('content', ''),
                parent_id=data.get('parent_id'),
                vault_id=vault_id,
                author_id=current_user_id
            )
            # `get_node_by_id` benötigt die user_id für die Berechtigungsprüfung
            return jsonify(database.get_node_by_id(new_node.id, vault_id, user_id=current_user_id)), 201
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403
        except Exception as e:
            logging.error(f"Error creating node: {e}")
            return jsonify({"error": "An internal server error occurred"}), 500

    @app.route('/api/nodes/<string:node_id>', methods=['PUT'])
    @jwt_required()
    def update_node(node_id):
        current_user_id = int(get_jwt_identity())
        data = request.json
        vault_id = data.get('vault_id')
        if not vault_id:
            return jsonify({"error": "vault_id is required"}), 400
        try:
            data.pop('vault_id', None)
            updated_node = database.update_node(node_id, vault_id, user_id=current_user_id, **data)
            return jsonify(updated_node.to_dict(include_content=True))
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route('/api/nodes/<string:node_id>', methods=['DELETE'])
    @jwt_required()
    def delete_node_endpoint(node_id):
        current_user_id = int(get_jwt_identity())
        try:
            vault_id = _get_vault_id_from_request()
            database.delete_node(node_id, vault_id=vault_id, user_id=current_user_id)
            return jsonify({"message": "Node deleted successfully"}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route('/api/nodes/move', methods=['POST'])
    @jwt_required()
    def move_node():
        current_user_id = int(get_jwt_identity())
        data = request.json
        vault_id = data.get('vault_id')
        node_id = data.get('node_id')
        new_parent_id = data.get('new_parent_id')
        if not vault_id or not node_id:
            return jsonify({"error": "vault_id and node_id are required"}), 400
        try:
            database.move_node(node_id, new_parent_id, vault_id=vault_id, user_id=current_user_id)
            return jsonify({"message": "Node moved successfully"})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route('/api/nodes/<string:node_id>/propose-update', methods=['POST'])
    @jwt_required()
    def propose_node_update(node_id):
        current_user_id = int(get_jwt_identity())
        data = request.json
        vault_id = data.get('vault_id')
        if not vault_id:
            return jsonify({"error": "vault_id is required"}), 400
        try:
            proposal = chatservice.propose_node_update_from_chat(
                target_node_id=node_id,
                chat_history=data.get('chat_history', []),
                context_node_ids=data.get('context_node_ids', []),
                model=data.get('model', 'gemini-1.5-pro-latest'),
                vault_id=vault_id,
                user_id=current_user_id
            )
            return jsonify(proposal)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route('/api/nodes/<node_id>/rename', methods=['PATCH'])
    @jwt_required()
    def rename_node(node_id):
        current_user_id = int(get_jwt_identity())
        data = request.get_json()
        new_title = data.get('title')
        vault_id = data.get('vault_id')

        if not new_title or not new_title.strip():
            return jsonify({"error": "New title cannot be empty"}), 400
        if not vault_id:
            return jsonify({"error": "vault_id is required"}), 400

        try:
            updated_node = database.rename_node(node_id, new_title.strip(), vault_id=vault_id, user_id=current_user_id)
            return jsonify(updated_node)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403
        except AttributeError:
            logging.error("database.rename_node function is not implemented.")
            return jsonify({"error": "Server-side function not implemented."}), 501

    # ==============================================================================
    # CHAT API
    # ==============================================================================
    @app.route('/api/llm/models', methods=['GET'])
    @jwt_required()
    def get_available_models():
        """Provides the list of available LLM models from the config."""
        # Access the configuration using Flask's `current_app` context
        models = app.config['AVAILABLE_LLM_MODELS']
        return jsonify(models)

    @app.route('/api/chat/sessions', methods=['GET'])
    @jwt_required()
    def list_chat_sessions():
        current_user_id = int(get_jwt_identity())
        try:
            vault_id = _get_vault_id_from_request()
            sessions = chatservice.list_sessions(vault_id=vault_id, user_id=current_user_id)
            return jsonify(sessions)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route('/api/chat/sessions/<string:session_id>', methods=['GET'])
    @jwt_required()
    def get_chat_session_history(session_id):
        current_user_id = int(get_jwt_identity())
        try:
            history = chatservice.get_session_history(session_id, user_id=current_user_id)
            return jsonify(history)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    ## WIEDERHERGESTELLT und für Multi-User angepasst (NON-STREAMING) ##
    @app.route('/api/chat/sessions', methods=['POST'])
    @jwt_required()
    def create_chat_session_non_stream():
        current_user_id = int(get_jwt_identity())
        data = request.get_json()
        try:
            vault_id = data.get('vault_id')
            if not vault_id:
                return jsonify({"error": "vault_id is required"}), 400

            user_input = data.get('user_input')
            if not user_input:
                return jsonify({"error": "User input is required"}), 400

            # HINWEIS: Sie müssen `chatservice.create_new_chat_session` anpassen,
            # damit es `user_id` akzeptiert und weitergibt.
            response_data = chatservice.create_new_chat_session(
                user_input=user_input,
                node_ids=data.get('node_ids', []),
                model=data.get('model', 'claude-3-sonnet-20240229'),
                vault_id=vault_id,
                user_id=current_user_id
            )
            return jsonify(response_data), 201
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403
        except Exception as e:
            logging.error(f"API Error creating chat session: {e}")
            return jsonify({"error": "Failed to create new chat session."}), 500

    ## WIEDERHERGESTELLT und für Multi-User angepasst (NON-STREAMING) ##
    @app.route('/api/chat/sessions/<string:session_id>/messages', methods=['POST'])
    @jwt_required()
    def add_message_to_session_non_stream(session_id):
        current_user_id = int(get_jwt_identity())
        data = request.get_json()
        user_input = data.get('user_input')
        if not user_input:
            return jsonify({"error": "User input is required"}), 400

        try:
            # HINWEIS: Sie müssen `chatservice.add_message_to_session` anpassen,
            # damit es `user_id` zur Autorisierung verwendet.
            response_data = chatservice.add_message_to_session(
                session_id=session_id,
                user_input=user_input,
                node_ids=data.get('node_ids', []),
                user_id=current_user_id
            )
            return jsonify(response_data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403
        except Exception as e:
            logging.error(f"API Error adding message to session {session_id}: {e}")
            return jsonify({"error": "Failed to process message."}), 500

    @app.route('/api/chat/sessions/<string:session_id>', methods=['DELETE'])
    @jwt_required()
    def delete_chat_session(session_id):
        current_user_id = int(get_jwt_identity())
        try:
            database.delete_chat_session(session_id, user_id=current_user_id)
            return jsonify({"message": f"Session with ID {session_id} deleted successfully."}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    # --- STREAMING CHAT ENDPOINTS ---
    @app.route('/api/chat/sessions/stream', methods=['POST'])
    @jwt_required()
    def stream_new_chat_session():
        current_user_id = int(get_jwt_identity())
        data = request.json
        vault_id = data.get('vault_id')
        user_input = data.get('user_input')
        #print("stream_new_chat_session", data.get('model', 'local'))
        if not vault_id or not user_input:
            return jsonify({"error": "vault_id and user_input are required"}), 400

        try:
            generator = chatservice.stream_new_chat_session(
                user_input=user_input,
                node_ids=data.get('node_ids', []),
                model=data.get('model', 'local'),
                vault_id=vault_id,
                user_id=current_user_id
            )

            def stream_with_context():
                with app.app_context(): yield from generator

            return Response(stream_with_context(), mimetype='text/event-stream')
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403

    @app.route('/api/chat/sessions/<string:session_id>/messages/stream', methods=['POST'])
    @jwt_required()
    def stream_message_to_session(session_id):
        current_user_id = int(get_jwt_identity())
        data = request.json
        user_input = data.get('user_input')
        model = data.get('model')

        if not user_input:
            return jsonify({"error": "user_input is required"}), 400

        try:
            # === THE FIX: Get the default model from the app config here ===
            default_model = app.config.get('DEFAULT_CHAT_MODEL', 'gpt-4o')  # Use a safe fallback

            generator = chatservice.stream_message_in_session(
                session_id=session_id,
                user_input=user_input,
                node_ids=data.get('node_ids', []),
                user_id=current_user_id,
                model=model,
                default_model_from_config=default_model
            )

            def stream_with_context():
                # The app_context is available here, but we've already extracted the config value
                with app.app_context():
                    yield from generator

            return Response(stream_with_context(), mimetype='text/event-stream')
        except PermissionError as e:
            return jsonify({"error": str(e)}), 403
        except ValueError as e:
            return jsonify({"error": str(e)}), 404

    @app.route('/api/chat/sessions/<string:session_id>/messages/<int:message_id>/retry', methods=['POST'])
    @jwt_required()
    def retry_stream_message(session_id, message_id):
        """
        MODIFIZIERT: Löst eine erneute Generierung einer spezifischen Assistenten-Nachricht aus.
        - Die Route konvertiert message_id jetzt direkt in einen Integer.
        - Die manuelle Validierung ist daher nicht mehr nötig.
        """
        current_user_id = int(get_jwt_identity())

        data = request.get_json() or {}
        model = data.get('model')

        try:
            # message_id ist jetzt garantiert ein Integer
            generator = chatservice.retry_specific_message_stream(
                session_id=session_id,
                message_id=message_id,
                user_id=current_user_id,
                model=model
            )

            def stream_with_context():
                with app.app_context():
                    yield from generator

            return Response(stream_with_context(), mimetype='text/event-stream')

        except Exception as e:
            logging.error(f"Failed to initiate retry for message {message_id} in session {session_id}: {e}",
                          exc_info=True)
            return jsonify({"error": "An internal server error occurred while trying to retry."}), 500

    # ==============================================================================
    # FILE SERVING & CLI
    # ==============================================================================
    # (Rest der Datei: /api/image, Frontend Serving, CLI Befehle sind identisch und korrekt)
    # ... Ihre CLI-Befehle und Frontend-Serving-Logik von oben ...
    @app.route('/api/image/<path:filename>')
    @jwt_required()
    def serve_secure_image(filename):
        try:
            return send_from_directory(SECURE_IMAGE_FOLDER, filename)
        except FileNotFoundError:
            return jsonify({"error": "Image not found"}), 404

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        if APP_ENV != 'production':
            return "This route is for production serving only. In dev, use the React dev server.", 404

        static_folder_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')
        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)
        else:
            return send_from_directory(static_folder_path, 'index.html')

    @app.cli.command('create-user')
    @click.argument('username')
    @click.argument('display_name')
    @click.argument('password')
    @click.option('--admin', is_flag=True, help='Make this user an administrator.')
    def create_user_command(username, password, display_name, admin):
        if User.query.filter_by(username=username).first():
            print(f"🔥 Error: User '{username}' already exists.")
            return
        user = User(username=username, display_name=display_name, user_type='human', is_admin=admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        admin_status = " as an administrator" if admin else ""
        print(f"✅ User '{username}' (Display: '{display_name}') created successfully{admin_status}.")

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