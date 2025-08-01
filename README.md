# Nexidion

> Nexidion is a private-first, self-hostable knowledge base for your most sensitive information. Self-host everything, trust no one.

This repository contains the full source code for the Nexidion application, including the Python/Flask backend and the React frontend.

## The Mission: A Private Vault, Not Just a Second Brain

Nexidion was born from a personal need for a knowledge management tool where privacy is not a feature, but the core architectural principle. Many tools aim to be your "second brain," focusing on productivity and interconnectivity. Nexidion's goal is different: to be your **private vault**.

It was designed for managing highly sensitive information where trust in third-party services is not an option. Unlike cloud-based or sync-dependent applications, Nexidion is an open-source web application designed from the ground up to be self-hosted on your own server, under your absolute control. The entire system, from the database to the optional, locally-connected AI, runs within your network. It is not a 'better Obsidian,' but a secure haven for your knowledge, accessible from any device with a web browser.

## Core Philosophy

*   **Privacy First:** Zero cloud-synchronization, zero telemetry, zero third-party tracking. Your data is yours alone.
*   **Total Control:** You run the software on your own hardware. You control access, backups, and any external connections.
*   **Verifiable Privacy:** The application is designed to have **zero external network calls by default**. Any connection to an external service (like an LLM API) is an explicit, opt-in configuration.
*   **Web-Based & Open Source:** Access your knowledge base from any modern web browser. The transparent, open-source code ensures there are no hidden surprises.

## Key Features

*   **Vaults:** Organize your knowledge into multiple, completely separate databases.
*   **Hierarchical Notes:** Structure your information in a familiar tree hierarchy.
*   **Rich Text Editing:** Write and format content using a clean Markdown editor.
*   **Full Version History:** Every change to a node is saved as a new version.
*   **Context-Aware AI Chat:** Engage in conversations with an AI that has access to only the nodes you select.
*   **Local LLM Support:** Connect to local LLMs (e.g., via Ollama) to ensure your sensitive documents and prompts never leave your local network.
*   **Orchestrator Engine & Workflows:** Define complex, multi-step workflows to automate knowledge processing, transforming Nexidion from a reactive tool into a proactive knowledge processing platform.
*   **Secure Multi-User Support:** Robust multi-user architecture using JWT for authentication and a full admin dashboard.

## Technical Architecture

*   **Backend:** Python, Flask, SQLAlchemy
*   **Asynchronous Tasks:** Celery and Redis for managing long-running AI operations.
*   **Database:** SQLite (default), PostgreSQL compatible.
*   **Frontend:** React.js, Vite

## Project Status

This project is under active development. The current focus is on implementing the **Orchestrator Engine (API 3.0)**, which represents a fundamental leap in capability from a reactive tool to a proactive, automated knowledge engine.

## Getting Started

### Local Development Setup

These instructions assume you are running both the backend and frontend on your local machine for development.

**Prerequisites:**

*   Python 3.10+
*   Node.js 18+

**1. Backend Setup**

The backend is a Flask application.

```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create and activate a virtual environment
python -m venv venv
# On Windows
.\venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate

# 3. Install required packages
pip install -r requirements.txt

# 4. (Optional) Install development packages
pip install -r requirements-dev.txt

# 5. Initialize the database
# This creates the initial SQLite database file.
flask init-db

# 6. Create an initial user
# Replace <username> and <password> with your desired credentials.
flask create-user <username> "Your Name" <password> --admin

# 7. Run the backend server
# The API will be available at http://127.0.0.1:5000
flask run
```

Leave this terminal running.

**2. Frontend Setup**

The frontend is a React application.

```bash
# 1. Open a new terminal and navigate to the frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Run the frontend development server
# The web application will be available at http://localhost:5173
npm run dev
```

You can now open `http://localhost:5173` in your browser and log in with the credentials you created.

## Configuration

The application is configured via environment variables, which can be placed in a `.env` file in the `backend` directory.

Key configuration options include:

*   `SECRET_KEY`: A strong, random secret for signing sessions.
*   `SQLALCHEMY_DATABASE_URI`: The connection string for your database (defaults to a local SQLite file).
*   `LLM_PROVIDER_API_KEYS`: API keys for external services like OpenAI, Anthropic, or Google.

Refer to `backend/config.py` for a full list of available configuration variables.

## Verifiable Privacy: Network Calls

As part of the "Privacy First" philosophy, Nexidion is designed to make **zero external network calls by default** after installation. All fonts and libraries are bundled.

The only external calls the application can make are **opt-in connections to Large Language Models (LLMs)**, which you must explicitly configure.

To maintain 100% data privacy, you can configure the application to use a locally-hosted LLM (e.g., via llama.cpp) by setting the appropriate base URL in your configuration. This ensures that your sensitive documents and prompts are never sent to a third-party service.
