# config.py
import os # Importiert, um mit dem Dateisystem (Pfade) zu arbeiten
from datetime import timedelta

# Findet den absoluten Pfad des Ordners, in dem diese Datei liegt.
# Das ist wichtig, damit der Pfad zur Datenbankdatei immer korrekt ist,
# egal von wo aus Sie das Skript starten.
basedir = os.path.abspath(os.path.dirname(__file__))

# Eine Klasse, die als Container für alle unsere Einstellungen dient.
class Config:
    ## --- DATABASE CONFIGURATION ---
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'knowledge_base.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # --- AUTHENTICATION & SECURITY ---
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8) # Increased from 1 to 8 as a suggestion
    
    # --- LLM & EXTERNAL SERVICES ---
    DEFAULT_CHAT_MODEL = os.getenv('DEFAULT_CHAT_MODEL', 'gemini-2.5-pro')
    LOCAL_LLM_URL = os.getenv('LOCAL_LLM_URL', 'http://localhost:1234/v1')

    # --- NEW: List of available LLM models for the frontend ---
    # This becomes the single source of truth for your entire application.
    AVAILABLE_LLM_MODELS = [
        {'id': 'claude-sonnet-4-20250514', 'name': 'claude sonnet 4'},
        {'id': 'gpt-4o', 'name': 'GPT-4o'},
        {'id': 'o4-mini-2025-04-16', 'name': 'o4 mini'},
        {'id': 'gpt-4.1-mini-2025-04-14', 'name': 'GPT-4.1'},
        {'id': 'gemini-2.5-pro', 'name': 'gemini-2.5-pro'},
        {'id': 'local', 'name': 'local'},
        {'id': 'mock', 'name': 'Mock LLM (Free Test)'},
        {'id': 'mock2', 'name': 'Mock2 LLM (Free Test)'}
    ]
    # It's also good practice to list all expected API keys here, even if they are just fetching from os.environ
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")