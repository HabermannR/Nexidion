from flask import Blueprint, send_from_directory, jsonify, current_app
from flask_jwt_extended import jwt_required


# Erstelle einen neuen Blueprint. Der erste Parameter 'images' ist der Name des Blueprints.
image_bp = Blueprint('images', __name__, url_prefix='/api/image')


# WICHTIG: Die Route hier ist nur der Teil, der NACH dem Prefix kommt,
# den wir bei der Registrierung festlegen.
@image_bp.route('/<path:filename>')
@jwt_required()
def serve_secure_image(filename):
    try:
        # Dies holt jetzt den korrekten, absoluten Pfad aus der Konfiguration
        secure_folder = current_app.config['SECURE_IMAGE_FOLDER']

        # Deine Debug-Ausgaben kannst du jetzt entfernen oder behalten, bis es läuft
        print(f"DEBUG: Suche in Ordner: '{secure_folder}' nach Datei: '{filename}'")

        return send_from_directory(secure_folder, filename)
    except FileNotFoundError:
        return jsonify({"error": "Image not found"}), 404