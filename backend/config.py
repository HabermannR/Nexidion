# config.py
import os # Importiert, um mit dem Dateisystem (Pfade) zu arbeiten

# Findet den absoluten Pfad des Ordners, in dem diese Datei liegt.
# Das ist wichtig, damit der Pfad zur Datenbankdatei immer korrekt ist,
# egal von wo aus Sie das Skript starten.
basedir = os.path.abspath(os.path.dirname(__file__))

# Eine Klasse, die als Container für alle unsere Einstellungen dient.
class Config:
    # Neue Konfigurationen für das sichere Auth-System
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
    ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH')

    # 2. SQLALCHEMY_DATABASE_URI:
    # Das ist die wichtigste Zeile für die Datenbank. Sie sagt SQLAlchemy:
    # "Deine Datenbank ist eine SQLite-Datei (`sqlite:///`) und sie befindet sich
    # in diesem Ordner (`basedir`) unter dem Namen `knowledge_base.db`."
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'knowledge_base.db')

    # 3. SQLALCHEMY_TRACK_MODIFICATIONS:
    # Eine Performance-Einstellung für SQLAlchemy. Wenn man sie auf False setzt,
    # spart die App Ressourcen, da sie nicht jede einzelne Änderung verfolgen muss.
    SQLALCHEMY_TRACK_MODIFICATIONS = False