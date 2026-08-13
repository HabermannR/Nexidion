# Contributing to Nexidion

Thank you for your interest in contributing! This document covers everything you need to get a full local development environment running, understand the project architecture, and submit quality pull requests.

---

## Table of Contents

1. [Project structure](#1-project-structure)
2. [Prerequisites](#2-prerequisites)
3. [Local development setup (Docker)](#3-local-development-setup-docker)
4. [Running without Docker](#4-running-without-docker)
5. [Environment variables](#5-environment-variables)
6. [Backend development](#6-backend-development)
7. [Frontend development](#7-frontend-development)
8. [The remark-internal-links plugin](#8-the-remark-internal-links-plugin)
9. [AI Task Runner](#9-ai-task-runner)
10. [Testing](#10-testing)
11. [Database migrations](#11-database-migrations)
12. [Pull request guidelines](#12-pull-request-guidelines)
13. [Known limitations & roadmap notes](#13-known-limitations--roadmap-notes)

---

## 1. Project structure

```text
Nexidion/
├── backend/                  # Python / Flask API
│   ├── api/                  # Route blueprints (nodes, vaults, auth, tasks, images, admin)
│   ├── services/             # Business logic layer
│   ├── models.py             # SQLAlchemy ORM models
│   ├── config.py             # App configuration loaded from env
│   ├── app.py                # Application factory & blueprint registration
│   ├── task_runner.py        # Autonomous AI background worker
│   └── Dockerfile.test       # Dedicated Dockerfile for the test suite
├── frontend/                 # React / Vite SPA
│   ├── src/
│   └── Dockerfile
├── remark-internal-links/    # Custom Remark plugin (local npm package)
├── docs/                     # User-facing documentation (markdown)
├── tests/                    # Pytest test suite
│   ├── Services/
│   ├── agent/
│   ├── api/
│   └── models/
├── docker-compose.yml        # Production compose file
├── docker-compose.dev.yml    # Development compose file (hot-reload & testing)
├── .env.example              # Template for local environment config
└── pyproject.toml            # Python project config, pytest settings, coverage
```

---

## 2. Prerequisites

| Tool | Minimum version | Notes |
| :--- | :--- | :--- |
| Docker | 24+ | Docker Compose v2 is required (`docker compose`, not `docker-compose`) |
| Docker Compose | v2 | Bundled with Docker Desktop; on Linux install the `docker-compose-plugin` |
| Node.js | 18+ | Only needed if working on the frontend or remark plugin outside Docker |
| Python | 3.11+ | Only needed if running the backend outside Docker |
| Git | any | — |

---

## 3. Local development setup (Docker)

The recommended way to develop is with the dedicated **development compose file**, which mounts your local code into the containers and enables hot-reloading for both the frontend (Vite HMR) and the backend (Flask debug mode).

### Step 1: Clone and configure

```bash
git clone https://github.com/HabermannR/Nexidion.git
cd Nexidion
cp .env.example .env
```

Edit `.env` and set at minimum:
- `JWT_SECRET_KEY` — any long random string
- `DB_PASSWORD` — any password (used only locally)

You do **not** need an `OPENAI_API_KEY` unless you want to test the AI Task Runner.

### Step 2: Start the development stack

```bash
docker compose -f docker-compose.dev.yml --profile with-postgres up --build
```

This starts three services:

| Service | Port | Description                                        |
| :--- | :--- |:---------------------------------------------------|
| `frontend` | 5173 | Vite dev server with HMR                           |
| `backend` | 5001 | Flask in debug mode, auto-restarts on file changes |
| `postgres` | 5432 | PostgreSQL 18 (exposed locally for DB clients)     |

Open **[http://localhost:5173](http://localhost:5173)** in your browser. The Vite dev server proxies API calls to the backend automatically.

> **Note:** The first build downloads Docker base images and installs dependencies — it may take a few minutes. Subsequent starts are fast.

### Step 3: (Optional) Enable the AI Task Runner

If you want to develop or test the Task Runner, add your `OPENAI_API_KEY` (or a local LLM URL — see [Section 9](#9-ai-task-runner)) to `.env`, then start with the extra profile:

```bash
docker compose -f docker-compose.dev.yml --profile with-postgres --profile with-task-runner up --build
```

### Stopping the stack

```bash
docker compose -f docker-compose.dev.yml down
```

To also remove the database volume (full reset):

```bash
docker compose -f docker-compose.dev.yml down -v
```

### Rebuilding after dependency changes

If you add a Python package (`requirements.txt`) or an npm package (`package.json`), rebuild the affected container:

```bash
docker compose -f docker-compose.dev.yml up --build backend
docker compose -f docker-compose.dev.yml up --build frontend
```

---

## 4. Running without Docker

If you prefer to run services directly on your host machine:

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export $(cat ../.env | xargs)   # Load env vars (adjust for your shell)
flask db upgrade
flask create-admin admin defaultPassword123
flask run --host=0.0.0.0 --port=5001 --debug
```

You will need a running PostgreSQL 16-18 instance reachable at the `DB_HOST`/`DB_PORT` configured in your `.env`.

### Frontend

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:5001 npm run dev
```

---

## 5. Environment variables

Copy `.env.example` to `.env` and adjust the values. All variables are loaded by Flask via `python-dotenv` and by Docker Compose automatically.

| Variable | Required | Default        | Description |
| :--- | :--- |:---------------| :--- |
| `JWT_SECRET_KEY` | Yes | —              | Secret for signing JWT tokens. Use a long random string in production. |
| `DB_HOST` | Yes | `postgres`     | Hostname of the PostgreSQL server. Use `localhost` when running outside Docker. |
| `DB_PORT` | Yes | `5432`         | PostgreSQL port. |
| `DB_NAME` | Yes | `nexidion`     | Database name. |
| `DB_USER` | Yes | —              | Database user. |
| `DB_PASSWORD` | Yes | —              | Database password. |
| `FLASK_ENV` | No | `production`   | Set to `development` to enable Flask debug mode outside Docker. |
| `OPENAI_API_KEY` | No | —              | API key for the AI Task Runner. Leave blank to disable. |
| `OPENAI_MODEL` | No | `gpt-5.6-luna` | Model name passed to the OpenAI API. The UI offers GPT-5.6 Luna, Terra, and Sol. |
| `OPENAI_BASE_URL` | No | OpenAI default | Override to point at a local LLM (e.g. Ollama). |
| `NEXIDION_POLL_INTERVAL` | No | `5`            | How often (seconds) the Task Runner polls for new tasks. |
| `ASSET_STORAGE_FOLDER` | No | `./asset_storage` | Persistent managed-image storage; mount it as a Docker volume. |

---

## 6. Backend development

The backend is a standard **Flask** application using **SQLAlchemy** (with Flask-Migrate for schema migrations) and **Flask-JWT-Extended** for authentication.

### Architecture

- **`app.py`** — application factory. Registers all blueprints and extensions.
- **`api/`** — thin route layer. Each blueprint handles HTTP concerns (parsing request JSON, returning responses) and delegates all logic to a service.
- **`services/`** — all business logic lives here. Services are plain Python classes/functions with no Flask dependency, which makes them straightforward to unit-test.
- **`models.py`** — SQLAlchemy models. Schema changes are always done via Alembic migrations (`flask db migrate`), never by hand.

### Secure image serving

Images are database-backed, vault-scoped assets. Both upload and download require
vault access, and the binary storage is configured with `ASSET_STORAGE_FOLDER`:

```markdown
![Alt text](/api/vaults/12/assets/asset-uuid)
```

Legacy folder references can be audited and converted with `flask
convert-legacy-images FOLDER`; it is a dry run unless `--apply` is supplied.

### Adding a new API endpoint

1. Add your route to the appropriate blueprint in `api/`, or create a new blueprint.
2. Implement the business logic in `services/`.
3. Register a new blueprint in `app.py` if you created one.
4. Write tests in `tests/api/` and `tests/Services/` (see [Section 10](#10-testing)).

---

## 7. Frontend development

The frontend is a **React** SPA built with **Vite**. It communicates with the backend exclusively via the REST API.

- `VITE_API_URL` controls the backend base URL. In the Docker dev setup this is set automatically to `http://localhost:5001`.
- Hot Module Replacement (HMR) is enabled in development — edits to `.jsx`/`.css` files are reflected in the browser instantly without a full reload.

### Linting

```bash
cd frontend
npm run lint
```

---

## 8. The remark-internal-links plugin

The `[[Node Name|uuid]]` internal link syntax is handled by a **custom Remark plugin** located in `remark-internal-links/`. It is a local npm package mounted into the frontend container via a volume.

During the Vite build, this plugin intercepts `[[...]]` syntax in Markdown and transforms it into `<span class="internal-link" data-target="..." data-display-text="...">` elements. This avoids React hydration crashes caused by block-level elements inside `<p>` tags.

If you modify the plugin:
- In Docker dev mode, the volume mount means changes are visible immediately after a Vite HMR cycle.
- Run `npm install` inside `frontend/` if you change `package.json` of the plugin, then rebuild the frontend container.

---

## 9. AI Task Runner

The Task Runner (`backend/task_runner.py`) is an autonomous Python worker that polls the database for tasks, executes them using an OpenAI-compatible LLM API, and writes results back to the vault.

### Using a local LLM for development

You do not need an OpenAI API key to develop or test the Task Runner. Any locally hosted LLM with an OpenAI-compatible endpoint works. Using [Ollama](https://ollama.com) as an example:

1. Install and start Ollama on your host machine with a model pulled (e.g. `ollama pull llama3`).
2. In your `.env`, set:
   ```
   OPENAI_BASE_URL=http://host.docker.internal:11434/v1
   OPENAI_API_KEY=ollama
   OPENAI_MODEL=llama3
   ```
3. Start the stack with `--profile with-task-runner`.

`host.docker.internal` resolves to your host machine from inside a Docker container on both macOS and Windows. On Linux, you may need to use your host's LAN IP instead, or add `--add-host=host.docker.internal:host-gateway` to the task-runner service in the compose file.

### Poll interval

The Task Runner sleeps between polls. The interval defaults to 5 seconds and is controlled by `NEXIDION_POLL_INTERVAL` in `.env`. During development you can set it lower (e.g. `1`) for faster feedback.

---

## 10. Testing

The test suite uses **pytest** with **pytest-cov** for coverage reporting.

### Running tests via Docker (Recommended)

We have a dedicated Docker service (`backend-test`) that automatically handles test database creation, configuration, and execution. Because it mounts your local directory, you can run tests continuously as you edit code.

To run the entire test suite, run:
```bash
docker compose -f docker-compose.dev.yml --profile with-postgres --profile test up backend-test
```
*(Add `--build` to the end if you recently modified `requirements-dev.txt` or the test Dockerfile).*

### Running tests locally (Without Docker)

If you are running the backend directly on your host machine via a virtual environment, simply ensure your local PostgreSQL server is running and run:
```bash
pytest
```

### Current coverage (v4.1)

This runs all 227 tests and prints a coverage report. HTML coverage output is written to `htmlcov/index.html`.

| Area | Coverage |
| :--- | :--- |
| Services | 92–100% |
| API routes | 83–100% |
| Models | 97% |
| `app.py` | 65%  |
| `images.py` | 54% |
| Overall | **89%** |

### Test structure

```text
tests/
├── Services/       # Unit tests for business logic (no HTTP, no DB)
├── agent/          # Task Runner behaviour
├── api/            # Integration tests for HTTP endpoints
└── models/         # ORM model tests
```

### Writing new tests

- Service tests should mock the database and test logic in isolation.
- API tests use Flask's test client and a test database (configured in `pyproject.toml`).
- Aim to keep coverage at or above 89% overall. New API endpoints need corresponding API tests.

---

## 11. Database migrations

Nexidion uses **Flask-Migrate** (Alembic) for schema management. Never alter the database schema directly.

```bash
# After changing models.py, generate a migration:
flask db migrate -m "describe your change"

# Review the generated file in migrations/versions/, then apply:
flask db upgrade

# Roll back the last migration:
flask db downgrade
```

> **Docker mode:** always run migration commands inside the backend container, not on your host shell. The hostname `postgres` only resolves inside Docker's network. Use:
> ```bash
> docker compose -f docker-compose.dev.yml exec backend flask db migrate -m "describe your change"
> docker compose -f docker-compose.dev.yml exec backend flask db upgrade
> ```

In Docker dev mode, `flask db upgrade` runs automatically on backend container start (see the `command` in `docker-compose.dev.yml`).

---

## 12. Pull request guidelines

- **Branch naming:** `feature/short-description`, `fix/short-description`, `docs/short-description`.
- **Commits:** Use clear, present-tense messages ("Add image upload endpoint", not "Added" or "WIP").
- **Tests:** All new backend features need tests. PRs that drop overall coverage below 89% will be asked to add tests before merge.
- **Migrations:** If your PR changes `models.py`, include the generated migration file.
- **Docs:** If your change affects user-facing behaviour, update the relevant file in `docs/`.
- **One concern per PR:** Keep PRs focused. A PR that adds a feature and refactors unrelated code is harder to review.

Before opening a PR, please run:

```bash
docker compose -f docker-compose.dev.yml --profile with-postgres --profile test up backend-test
cd frontend && npm run lint
```

---

## 13. Known limitations & roadmap notes

These are tracked issues that contributors should be aware of before touching the related areas:

- **AI buttons always visible:** The frontend currently shows AI Agent UI controls even when no Task Runner is running. Tasks queue silently to `pending` with no user feedback. A worker-status endpoint to drive dynamic UI hiding is a known open item.
- **Lock icon protects content, not title:** Both the write-lock (`bxs-lock-alt`) and full-privacy lock (`bxs-no-entry`) still allow the agent to see a node's title and tree position. Only the content body is protected. If the title itself is sensitive, use a generic name.
- **FTS languages:** Full-text search currently supports English and German. Adding more languages requires a schema migration to add additional `tsvector` columns or a language-aware trigger.
