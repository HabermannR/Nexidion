# Running Nexidion on bare metal

This guide runs Nexidion directly on Windows or Linux without Docker. Nexidion
has two independent Python processes:

1. the web/API server (`serve.py`), and
2. the AI task runner (`task_runner.py`).

Starting only the web server leaves AI Actions and queued PDF curation jobs in
`pending`. Keep both terminals open whenever AI work should run.

## Tomorrow morning: start an existing installation

These commands assume PostgreSQL, the Python environment, `.env`, and the built
frontend already exist.

### Windows PowerShell

First ensure the Windows PostgreSQL service is running. Its exact name depends
on the installed version:

```powershell
Get-Service *postgres* | Start-Service
```

Open PowerShell terminal 1 in the Nexidion repository:

```powershell
cd C:\path\to\Nexidion
.\.venv\Scripts\Activate.ps1
python serve.py
```

Open PowerShell terminal 2 in the same repository:

```powershell
cd C:\path\to\Nexidion
.\.venv\Scripts\Activate.ps1
python task_runner.py
```

Do not close terminal 2. It is the worker that consumes AI Actions, summary jobs,
and AI-assisted PDF curation.

Open <http://localhost:5001>. A quick web/API check is:

```powershell
Invoke-WebRequest http://localhost:5001/api/system/config -UseBasicParsing
```

The task-runner terminal must remain running and must not show either of these
startup errors:

```text
ERROR: No local, OpenAI, or OpenRouter LLM provider is configured
ERROR: No LLM agent user found
```

### Linux

```bash
sudo systemctl start postgresql
cd /path/to/Nexidion
source .venv/bin/activate
python serve.py
```

In a second terminal:

```bash
cd /path/to/Nexidion
source .venv/bin/activate
python task_runner.py
```

Then open <http://localhost:5001>. Verify the API with:

```bash
curl --fail http://localhost:5001/api/system/config
```

## First-time installation

### Prerequisites

- Python 3.10 or newer
- Node.js 20 and npm
- PostgreSQL 16–18
- Git
- At least one LLM provider: OpenRouter, OpenAI, or a local OpenAI-compatible
  server such as LM Studio or Ollama

Run all project commands below from the repository root, not from `backend/`.

### 1. Create PostgreSQL database and user

Use pgAdmin or `psql` as a PostgreSQL administrator. Choose your own password:

```sql
CREATE USER nexidion_user WITH PASSWORD 'replace-with-a-strong-password';
CREATE DATABASE nexidion OWNER nexidion_user;
```

If the database and user already exist, do not recreate them.

### 2. Configure Nexidion

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Linux equivalent:

```bash
cp .env.example .env
```

At minimum, set these values in `.env`:

```dotenv
FLASK_ENV="production"
APP_ENV="production"
JWT_SECRET_KEY="replace-with-a-long-random-secret"

DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="nexidion"
DB_USER="nexidion_user"
DB_PASSWORD="the-password-created-above"

ASSET_STORAGE_FOLDER="C:/NexidionData/assets"
```

On Linux, use an absolute Linux path for `ASSET_STORAGE_FOLDER`. Preserve this
folder when backing up Nexidion.

Configure at least one provider. For OpenRouter:

```dotenv
OPENROUTER_API_KEY="your-key"
OPENROUTER_MODEL="deepseek/deepseek-v4-flash-0731"
```

For a local LM Studio-compatible endpoint:

```dotenv
LOCAL_LLM_URL="http://127.0.0.1:1234/v1"
LOCAL_LLM_API_KEY="not-needed"
LOCAL_LLM_MODEL="the-loaded-model-id"
```

Do not set `DOCKER_LOCAL_LLM_URL` for a bare-metal installation. That variable is
only the Docker host-bridge override.

Keep this safe default unless actively debugging model streams:

```dotenv
NEXIDION_CAPTURE_STREAM_PAYLOADS=false
```

### 3. Install the Python application

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

If PowerShell blocks virtual-environment activation, allow locally created
scripts for your user and then retry:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 4. Build the frontend

```powershell
cd frontend
npm ci
npm run build
cd ..
```

The same commands work in Linux. `serve.py` serves `frontend/dist`, so rebuilding
is required after frontend source changes.

### 5. Initialize or upgrade the database

With the virtual environment active, from the repository root:

```powershell
python -m flask --app wsgi:app db upgrade
python -m flask --app wsgi:app create-llm-agent
```

For a new installation only, create the first administrator. Replace both values:

```powershell
python -m flask --app wsgi:app create-admin admin "replace-with-a-strong-password"
```

The commands are identical on Linux.

### 6. Start both Nexidion processes

Use the two-terminal procedure at the top of this document:

```text
Terminal 1: python serve.py
Terminal 2: python task_runner.py
```

The web/API server uses port 5001 by default. Override it with
`NEXIDION_PORT` in `.env` if necessary.

## Updating an existing checkout

Stop the web server and task runner with `Ctrl+C`, then:

```powershell
git pull
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m flask --app wsgi:app db upgrade
cd frontend
npm ci
npm run build
cd ..
```

Restart both terminals afterward. On Linux, use
`source .venv/bin/activate` instead of the PowerShell activation command.

## Troubleshooting

### Tasks remain pending

The task runner is not running, cannot reach PostgreSQL, or exited during startup.
Start `python task_runner.py` in its own visible terminal and read its error.

### The web UI works but AI Actions do nothing

The web/API and task runner are separate. A working browser proves only that
`serve.py` is running.

### Database connection fails

Confirm that PostgreSQL is running and `.env` uses `DB_HOST="localhost"`, not the
Docker service hostname `postgres`.

Windows check:

```powershell
Get-Service *postgres*
Test-NetConnection localhost -Port 5432
```

Linux check:

```bash
systemctl status postgresql
pg_isready -h localhost -p 5432
```

### AI provider is reported as unconfigured

Set at least one of `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, or `LOCAL_LLM_URL` in
the repository-root `.env`, then restart the task runner.

### Frontend is missing or stale

Run `npm ci` and `npm run build` inside `frontend/`, then restart `serve.py` and
force-refresh the browser.

### Check a streamed task response

From the repository root with the virtual environment active:

```powershell
python -m agent.stream_debug TASK_ID --follow
```

Payload capture is intentionally off by default because payloads may contain note
content.
