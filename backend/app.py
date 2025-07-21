# app.py
import os
import sys

# Füge das Projekt-Hauptverzeichnis zum Python-Pfad hinzu
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
import click

# Umgebungsvariablen laden
load_dotenv()

from backend.config import Config
from backend.models import db, User

# API Blueprints importieren
from backend.api.auth import auth_bp
from backend.api.vaults import vaults_bp
from backend.api.nodes import nodes_bp
from backend.api.chats import chats_bp
from backend.api.llm import llm_bp
from backend.api.images import image_bp

migrate = Migrate()


def create_app(config_class=Config):
    """Application Factory Pattern"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    app = Flask(__name__)
    app.config.from_object(config_class)

    # CORS-Konfiguration für Entwicklung
    APP_ENV = os.getenv('APP_ENV', 'development')

    if APP_ENV == 'production':
        print("----> Running in PRODUCTION mode")

    else:
        print("----> Running in DEVELOPMENT mode with CORS")

        # Holen Sie die IP aus der .env-Datei, wie es vorher war.
        # Das ist wichtig, damit Ihr Frontend von einem anderen Gerät im LAN zugreifen kann.
        local_ip = os.getenv("LOCAL_IP", "192.168.2.59")

        allowed_origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            f"http://{local_ip}:5173"
        ]
        CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)

    if not app.config['JWT_SECRET_KEY']:
        raise ValueError("JWT_SECRET_KEY must be set in your .env file.")

    # Erweiterungen initialisieren
    db.init_app(app)
    migrate.init_app(app, db)
    JWTManager(app)

    # API Blueprints registrieren
    app.register_blueprint(auth_bp)
    app.register_blueprint(vaults_bp)
    app.register_blueprint(nodes_bp)
    app.register_blueprint(chats_bp)
    app.register_blueprint(llm_bp)
    app.register_blueprint(image_bp, url_prefix='/api/image')

    # --- CLI Befehle (bereinigt) ---
    register_cli_commands(app)

    # --- Frontend Serving (für Produktion) ---
    register_frontend_serving(app)

    return app


def register_frontend_serving(app):
    """Kümmert sich um das Ausliefern des Frontend-Builds in Produktion."""

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        if os.getenv('FLASK_ENV') != 'production':
            return "Frontend serving is disabled in development. Use the React dev server.", 404

        static_folder_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')
        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)
        else:
            return send_from_directory(static_folder_path, 'index.html')


def register_cli_commands(app):
    """Registriert die verbleibenden, nützlichen CLI-Befehle."""

    @app.cli.command('create-admin')
    @click.argument('username')
    @click.argument('password')
    @click.option('--display-name', default=None, help='Optional display name for the user.')
    def create_admin_command(username, password, display_name):
        """Creates a new administrator user."""
        if User.query.filter_by(username=username).first():
            print(f"🔥 Error: User '{username}' already exists.")
            return

        # Wenn kein Anzeigename gegeben ist, den Benutzernamen verwenden
        display_name = display_name or username.capitalize()

        user = User(username=username, display_name=display_name, user_type='human', is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"✅ Administrator '{username}' created successfully.")


# --- App Ausführung (nur für lokale Entwicklung) ---
if __name__ == '__main__':
    app = create_app()
    # debug=True wird durch FLASK_DEBUG=1 in .env gesteuert, was besser ist
    app.run(host='0.0.0.0', port=5001)