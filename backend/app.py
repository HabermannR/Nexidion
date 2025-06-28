# app.py
import os
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, JWTManager

# Load environment variables from .env file, especially for local development
load_dotenv()

from config import Config
from models import db
import database
import llm


#To Run Locally:
#Terminal 1 (Backend): Navigate to your backend folder and run python app.py.
#Terminal 2 (Frontend): Navigate to your frontend folder and run npm start (or npm run dev).

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
    jwt = JWTManager(app) # JWT initialisieren

    # --- API-Routen (No changes needed here) ---

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

    # ... (all your other API routes remain exactly the same) ...
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

    @app.route('/api/nodes/<node_id>', methods=['PUT'])
    @jwt_required()
    def update_node(node_id):
        data = request.json
        title, content = data.get('title'), data.get('content')
        if title is None or content is None:
            return jsonify({"error": "Title and content are required"}), 400
        try:
            updated_node = database.update_node(node_id, title, content)
            return jsonify(updated_node)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404

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

    @app.route('/api/chat', methods=['POST'])
    @jwt_required()
    def handle_chat():
        data = request.get_json()
        user_input, chat_history, model, context_content = (
            data.get('user_input'), data.get('chat_history', []),
            data.get('model', 'claude-3-sonnet-20240229'), data.get('context_content', '')
        )
        if not user_input:
            return jsonify({"error": "User input is required"}), 400
        try:
            system_prompt = "You are a helpful assistant for a knowledge base. Answer the user's question based using the provided context and your own knowledge."
            context_enhanced_input = (f"<context>\n{context_content}\n</context>\n\nMy question is: {user_input}")
            messages = chat_history + [{"role": "user", "content": context_enhanced_input}]
            assistant_response = llm.generate_response(prompt_or_messages=messages, system_prompt=system_prompt,
                                                       model=model)
            return jsonify({"content": assistant_response})
        except Exception as e:
            logging.error(f"Error during LLM API call in /api/chat: {e}")
            return jsonify({"error": "Failed to communicate with the language model."}), 500

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

    return app


# --- App Ausführung (For local development ONLY) ---
# This block is NOT run on PythonAnywhere.
if __name__ == '__main__':
    # We call create_app() which will automatically run in 'development' mode
    # because the APP_ENV variable is not set.
    app = create_app()
    app.run(host='0.0.0.0', port=5001, debug=True)