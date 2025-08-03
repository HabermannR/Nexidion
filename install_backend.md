# Nexidion Backend

This repository contains the backend service for the Nexidion project. It is built using Flask and SQLAlchemy, and provides a robust API for handling application data and interacting with various Large Language Model (LLM) services.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Setup and Installation](#setup-and-installation)
- [Environment Configuration](#environment-configuration)
- [Running the Application](#running-the-application)
- [Testing and Coverage Analysis](#testing-and-coverage-analysis)
  - [Running the Tests](#running-the-tests)
    - [1. Standard Tests (Default - No API Calls)](#1-standard-tests-default---no-api-calls)
    - [2. Running LLM-Specific Tests (Local or Cloud)](#2-running-llm-specific-tests-local-or-cloud)
  - [How LLM Tests are Identified](#how-llm-tests-are-identified)
  - [Understanding the Coverage Report](#understanding-the-coverage-report)
- [Advanced: Analyzing Missing Coverage](#advanced-analyzing-missing-coverage-with-annotate_coveragepy)

---

## Prerequisites

Before you begin, ensure you have the following installed:
- [Python](https://www.python.org/downloads/) (>= 3.8)
- [Git](https://git-scm.com/)
- An active shell environment (e.g., WSL2 on Windows, or a native Linux/macOS terminal).

---

## Setup and Installation

Follow these steps to get your development environment set up and running.

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/HabermannR/Nexidion
    cd Nexidion
    ```

2.  **Create and Activate a Virtual Environment**
    It is crucial to use a virtual environment to manage project dependencies.
    ```bash
    # Create the virtual environment (e.g., named 'venv')
    python3 -m venv venv

    # Activate it (for Linux/macOS/WSL)
    source venv/bin/activate
    ```
    Your terminal prompt should now be prefixed with `(venv)`.

3.  **Install All Dependencies**
    This project uses `pyproject.toml` to manage all production and development dependencies. The following command installs everything you need in one step.
    ```bash
    pip install -e ".[test,dev]"
    ```
    - `-e`: Installs the project in "editable" mode, so your code changes are immediately effective.
    - `".[test,dev]"`: Installs all packages listed in the main `dependencies` list as well as the optional `[test]` and `[dev]` groups.

---

## Environment Configuration

The application requires API keys and other configuration to be set as environment variables. It is designed to load these from a `.env` file in the project root.

1.  **Create a `.env` file**
    It's recommended to copy the example file to create your local configuration:
    ```bash
    cp .env.example .env
    ```

2.  **Edit the `.env` file**
    Open the newly created `.env` file and fill in the required values. Below is a complete example reflecting all possible configurations from `config.py`.

    ```dotenv
    # .env.example

    # --- Flask & Application Configuration ---
    # These are standard Flask variables.
    APP_ENV=development

    # --- Security ---
    # IMPORTANT: Generate your own secret key for JWT token signing.
    # You can use this command in your terminal: python -c 'import secrets; print(secrets.token_hex(24))'
    JWT_SECRET_KEY="your-super-secret-key-here"

    # --- Database Configuration ---
    # The application defaults to a local SQLite database. You only need to set this if you
    # want to use a different database (e.g., PostgreSQL).
    # SQLALCHEMY_DATABASE_URI="postgresql://user:password@host/dbname"

    # --- API Keys for Cloud LLMs ---
    # Fill in the keys for any cloud services you plan to use. Leave blank if unused.
    OPENAI_API_KEY=""
    ANTHROPIC_API_KEY=""
    GEMINI_API_KEY=""

    # --- Configuration for Local LLMs ---
    # URL for a local LLM server (e.g., LM Studio, Ollama with OpenAI compatibility)
    LOCAL_LLM_URL="http://localhost:1234/v1"

    # Optional API key for a local LLM. Many servers don't require one,
    # but some accept a placeholder like "not-needed" or a specific key.
    LOCAL_LLM_API_KEY=""
    ```

---

## Running the Application

Once your virtual environment is active and your `.env` file is configured, you can start the Flask development server:

```bash
flask run
```

---

## Testing and Coverage Analysis

This project features a powerful, flexible testing framework that allows you to control which tests are run, especially those interacting with external LLM APIs. The necessary `--cov` flags for coverage reporting are automatically applied from your `pyproject.toml` configuration.

### Running the Tests

#### 1. Standard Tests (Default - No API Calls)

This is the **recommended command for most development work**. It runs all unit and integration tests that do **not** depend on an LLM. It's fast, free, and runs entirely offline.

```bash
pytest
```

By default, any test that requires an LLM will be skipped automatically, so this simple command is the safest and quickest way to check your code.

#### 2. Running LLM-Specific Tests (Local or Cloud)

To run the end-to-end tests that interact with LLMs, use the `--llm` command-line flag. This gives you fine-grained control over which models to test against.

> **⚠️ CAUTION: Running tests against cloud models (Gemini, OpenAI, Claude) will make real API calls and may incur costs on your account.**

**Prerequisite**: For any cloud model, you must have its API key set in your `.env` file (e.g., `GEMINI_API_KEY`). If the key is missing, tests for that specific model will be automatically and safely skipped.

**Common Commands:**

-   **Run against the local LLM only:**
    ```bash
    pytest --llm=local
    ```

-   **Run against OpenAI only:**
    ```bash
    pytest --llm=openai
    ```

-   **Run against the local model and Claude:**
    ```bash
    pytest --llm=local-claude
    ```

-   **Run against all configured LLMs (local and cloud):**
    ```bash
    pytest --llm=all
    ```

### How LLM Tests are Identified

Instead of using markers, our test suite uses `pytest`'s dynamic parametrization. Tests that need to run against an LLM simply request the `llm_model_name` fixture in their function signature.

The test runner then automatically creates a version of that test for each model specified by the `--llm` flag.

```python
# This test will be automatically duplicated for each model you choose to run.
def test_generate_text_with_llm(client, auth_headers_persistent, llm_model_name):
    """
    This test will be run against 'local', 'gemini', etc.,
    depending on the --llm flag.
    """
    response = client.post(
        '/api/v1/generate',
        headers=auth_headers_persistent,
        json={
            'prompt': 'Tell me a joke.',
            'model': llm_model_name  # The fixture provides the model name here
        }
    )
    assert response.status_code == 200
    # ... more assertions
```

### Understanding the Coverage Report

Running `pytest` generates two reports showing how much of your code is exercised by the tests.

#### Terminal Report (`term-missing`)

This option prints a summary table directly into your terminal. The **Missing** column is the most important, as it shows the specific line numbers or ranges that are not covered by tests.

```
Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
backend/api/nodes.py                  148     27    82%   43-44, 65, 110-115
...
-----------------------------------------------------------------
TOTAL                                1234    200    84%
```

#### HTML Report (`html`)

This option generates a detailed, interactive HTML report in a new `htmlcov/` directory. **To view it, open the `htmlcov/index.html` file in your web browser.** This report visually highlights covered (green) and uncovered (red) lines of code.

---

## Advanced: Analyzing Missing Coverage with `annotate_coverage.py`

When you find a file with low coverage, the `annotate_coverage.py` script is a powerful tool to help write new tests, especially when used with an LLM assistant.

### What This Script Does

The script takes a single line of output from the `term-missing` report and creates a new, annotated `.txt` file. In this new file, it wraps the original code in `<covered>` and `<missing>` tags, making it crystal clear which parts of the code lack test coverage.

### Workflow: How to Use It with an LLM

1.  **Get the Coverage Report**
    Run the tests and find a line in the terminal report you want to improve.
    ```bash
    pytest
    ```
    ```
    # Example output line:
    backend\api\nodes.py                  148     27    82%   43-44, 65, 110-115
    ```

2.  **Run the Annotation Script**
    Copy that entire line and pass it to the script as a single string argument. **Use quotes to ensure it's treated as one argument.**
    ```bash
    python backend/scripts/annotate_coverage.py "backend\api\nodes.py                  148     27    82%   43-44, 65, 110-115"
    ```
    This creates a file named `backend/api/nodes.py.annotated.txt`.

3.  **Use the Annotated File with an LLM**
    Open the generated `.annotated.txt` file, copy its content, and paste it into your favorite LLM (e.g., ChatGPT, Claude, Gemini) with the following prompt.

    **Example Prompt for the LLM:**
    > Hello! Below is a Python file from my project, annotated with test coverage information. The code wrapped in `<missing>` tags is not currently covered by any tests.
    >
    > Please write new `pytest` tests that specifically target and cover the code inside the `<missing>` blocks. Make sure the new tests are clear, robust, and follow best practices for `pytest`.
    >
    > ```python
    > # ... paste the content of the .annotated.txt file here ...
    > ```

