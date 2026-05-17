import os
import sys

# Add the project root directory to the Python path
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

# Load environment variables
load_dotenv()

from backend.config import Config
from backend.models import db, User, UserType

# Import API Blueprints
from backend.api.auth import auth_bp
from backend.api.vaults import vaults_bp
from backend.api.nodes import nodes_bp
from backend.api.images import image_bp
from backend.api.admin import admin_bp
from backend.api.tasks import tasks_bp

migrate = Migrate()


def create_app(config_class=Config):
    """Application Factory Pattern"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    app = Flask(__name__)
    app.config.from_object(config_class)

    # CORS configuration for development
    APP_ENV = os.getenv('APP_ENV', 'development')

    if APP_ENV == 'production':
        print("----> Running in PRODUCTION mode")

    else:
        print("----> Running in DEVELOPMENT mode with CORS")

        # Get the IP from the .env file, as it was before.
        # This is important so your frontend can be accessed from another device on the LAN.
        local_ip = os.getenv("LOCAL_IP", "192.168.2.59")

        allowed_origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            f"http://{local_ip}:5173"
        ]
        CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)

    if not app.config['JWT_SECRET_KEY']:
        raise ValueError("JWT_SECRET_KEY must be set in your .env file.")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    JWTManager(app)

    # Register API Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(vaults_bp)
    app.register_blueprint(nodes_bp)
    app.register_blueprint(image_bp, url_prefix='/api/image')
    app.register_blueprint(admin_bp)
    app.register_blueprint(tasks_bp)

    # --- CLI Commands (cleaned up) ---
    register_cli_commands(app)

    # --- Frontend Serving (for production) ---
    register_frontend_serving(app)

    return app


def register_frontend_serving(app):
    """Handles serving the frontend build in production."""

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
    """Registers the remaining useful CLI commands."""

    @app.cli.command('create-admin')
    @click.argument('username')
    @click.argument('password')
    @click.option('--display-name', default=None, help='Optional display name for the user.')
    def create_admin_command(username, password, display_name):
        """Creates a new administrator user."""
        if User.query.filter_by(username=username).first():
            print(f"🔥 Error: User '{username}' already exists.")
            return

        # If no display name is provided, use the username
        display_name = display_name or username.capitalize()

        user = User(username=username, display_name=display_name, user_type=UserType.HUMAN, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"✅ Administrator '{username}' created successfully.")

    @app.cli.command('create-llm-agent')
    def create_llm_agent_command():
        """Creates the default LLM agent user with a fixed ID of 2, if it doesn't exist."""
        existing = User.query.filter_by(username='default-llm').first()
        if existing:
            print(f"✅ LLM agent already exists (ID: {existing.id}).")
            return

        agent = User(
            username='default-llm',
            display_name='LLM Assistant',
            # Update user_type here to use the Enum
            user_type=UserType.LLM_ASSISTANT,
            is_admin=False,
        )
        db.session.add(agent)
        db.session.flush()  # assigns the ID before commit

        if agent.id != 2:
            print(f"⚠️  Warning: LLM agent got ID {agent.id}, expected 2. "
                  "Make sure admin (ID 1) is created first.")

        db.session.commit()
        print(f"✅ LLM agent '{agent.username}' created (ID: {agent.id}).")


# --- App Execution (for local development only) ---
if __name__ == '__main__':
    app = create_app()
    # debug=True is controlled by FLASK_DEBUG=1 in .env, which is better
    app.run(host='0.0.0.0', port=5001)