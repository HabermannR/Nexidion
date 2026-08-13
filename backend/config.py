import os
from datetime import timedelta

# `basedir` is the absolute path to the 'backend' folder, as this is where config.py is located.
# e.g., C:\...\KnowledgeBase\backend or /home/user/KnowledgeBase/backend
basedir = os.path.abspath(os.path.dirname(__file__))

# Define the project root by navigating one level up from 'basedir'.
# This is the most robust way to get the main directory of your project.
project_root = os.path.dirname(basedir)


class Config:
    ## --- IMAGE FOLDER CONFIGURATION ---
    # Construct the path using the project root and the folder name.
    ASSET_STORAGE_FOLDER = os.getenv('ASSET_STORAGE_FOLDER', os.path.join(project_root, 'asset_storage'))

    ## --- DATABASE CONFIGURATION ---
    # Fetch DB details from environment variables
    DB_USER = os.getenv('DB_USER', 'default_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'default_password')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'Nexidion')

    # Build the PostgreSQL connection URI
    SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- AUTHENTICATION & SECURITY ---
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)  # Increased from 1 to 8 as a suggestion

    # --- LLM & EXTERNAL SERVICES ---
    LOCAL_LLM_URL = os.getenv('LOCAL_LLM_URL', 'http://localhost:1234/v1')

    # It's also good practice to list all expected API keys here, even if they are just fetching from os.environ
    # ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
