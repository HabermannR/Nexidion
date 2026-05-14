# config.py
import os
from datetime import timedelta

# `basedir` ist hier der absolute Pfad zum 'backend'-Ordner, da hier die config.py liegt.
# z.B. C:\...\KnowledgeBase\backend oder /home/user/KnowledgeBase/backend
basedir = os.path.abspath(os.path.dirname(__file__))

# NEU: Definiere den Projekt-Root, indem du eine Ebene von 'basedir' nach oben gehst.
# Das ist der robusteste Weg, um zum Hauptverzeichnis deines Projekts zu gelangen.
project_root = os.path.dirname(basedir)


class Config:
    ## --- IMAGE FOLDER CONFIGURATION ---
    # Wir setzen den Pfad aus dem Projekt-Root und dem Ordnernamen zusammen.
    SECURE_IMAGE_FOLDER = os.path.join(project_root, 'secure_images')

    ## --- DATABASE CONFIGURATION ---
    # Hole die DB-Details aus den Umgebungsvariablen
    DB_USER = os.getenv('DB_USER', 'default_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'default_password')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'default_db')

    # Baue die PostgreSQL-Verbindungs-URI zusammen
    SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # --- AUTHENTICATION & SECURITY ---
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8) # Increased from 1 to 8 as a suggestion
    
    # --- LLM & EXTERNAL SERVICES ---
    LOCAL_LLM_URL = os.getenv('LOCAL_LLM_URL', 'http://localhost:1234/v1')


    # It's also good practice to list all expected API keys here, even if they are just fetching from os.environ
    #ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    #GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY")