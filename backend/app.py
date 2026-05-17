import os
import logging
from datetime import datetime, timezone

from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from backend.extensions import limiter
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
load_dotenv()

from backend.config import Config
from backend.models import db, User, VaultAccess, Vault

# Import API Blueprints
from backend.api.auth import auth_bp
from backend.api.vaults import vaults_bp
from backend.api.nodes import nodes_bp
from backend.api.images import image_bp
from backend.api.admin import admin_bp
from backend.api.tasks import tasks_bp
from backend.api.system import system_bp
from backend.cli import register_commands

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
    limiter.init_app(app)

    # Explicitly set the migrations directory
    backend_dir = os.path.abspath(os.path.dirname(__file__))
    migrations_dir = os.path.join(backend_dir, 'migrations')
    migrate.init_app(app, db, directory=migrations_dir)

    JWTManager(app)

    # Register API Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(vaults_bp)
    app.register_blueprint(nodes_bp)
    app.register_blueprint(image_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(system_bp)

    # CLI Commands
    register_commands(app)

    # Frontend Serving (for production)
    register_frontend_serving(app)

    # Guest cleanup scheduler
    def _cleanup_expired_guests():
        with app.app_context():
            expired = User.query.filter(
                User.is_guest == True,
                User.expires_at < datetime.now(timezone.utc)
            ).all()
            for user in expired:
                for vault in Vault.query.filter_by(owner_id=user.id).all():
                    db.session.delete(vault)
                VaultAccess.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
            if expired:
                db.session.commit()

    scheduler = BackgroundScheduler()
    scheduler.add_job(_cleanup_expired_guests, 'interval', hours=1)
    scheduler.start()

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