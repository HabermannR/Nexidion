# Testing and Coverage Analysis

This document explains how to run the project's test suite, understand the test coverage reports, and use our custom script to help write new tests.

## Table of Contents

- [Running the Tests](#running-the-tests)
  - [Standard Tests (Fast, Free, No API Calls)](#1-standard-tests-fast-free-no-api-calls)
  - [All Tests (Including Paid LLM API Calls)](#2-all-tests-including-paid-llm-api-calls)
- [Understanding the Test Types](#understanding-the-test-types)
  - [What are `llm` tests?](#what-are-llm-tests)
  - [Which Tests Cost Money?](#which-tests-cost-money)
- [Understanding the Coverage Report](#understanding-the-coverage-report)
  - [Terminal Report (`term-missing`)](#terminal-report-term-missing)
  - [HTML Report (`html`)](#html-report-html)
- [Advanced: Analyzing Missing Coverage with `annotate_coverage.py`](#advanced-analyzing-missing-coverage-with-annotate_coveragepy)
  - [What This Script Does](#what-this-script-does)
  - [Workflow: How to Use It with an LLM](#workflow-how-to-use-it-with-an-llm)

---

## Running the Tests

We have two primary ways to run tests, depending on whether you want to include tests that interact with external, paid Large Language Model (LLM) APIs.

### 1. Standard Tests (Fast, Free, No API Calls)

This is the **recommended command for most development work**. It runs all unit and integration tests that do not require external API calls.

```bash
pytest -m "not llm" --cov=backend --cov-report=term-missing --cov-report=html
```

- `-m "not llm"`: This tells `pytest` to run all tests **except** those marked with the `llm` label.
- `--cov=backend`: This measures code coverage for the `backend` directory.
- `--cov-report=...`: This specifies the formats for the coverage report (explained below).

### 2. All Tests (Including Paid LLM API Calls)

This command runs the **entire test suite**, including tests that make real API calls to services like Google Gemini or Anthropic Claude.

> **⚠️ CAUTION: Running these tests will make real API calls and will incur costs on your account.**

**Prerequisite**: You must set the required API keys as environment variables. For example, based on the test code, you need to set `GEMINI_API_KEY`.

```bash
# For Windows (Command Prompt)
set GEMINI_API_KEY=your_api_key_here

# For Windows (PowerShell)
$env:GEMINI_API_KEY="your_api_key_here"

# For Linux/macOS
export GEMINI_API_KEY="your_api_key_here"
```

Once the key is set, run the full test suite:

```bash
pytest --cov=backend --cov-report=term-missing --cov-report=html
```

If you run this command without setting the API key, the `llm` tests will be automatically skipped.

## Understanding the Test Types

### What are `llm` tests?

In our codebase, we use a custom `pytest` marker, `@pytest.mark.llm`, to identify specific tests.

```python
@pytest.mark.llm
def test_stream_new_message_service_with_real_claude_llm(...):
    # ... test logic that calls a real LLM API ...
```

This marker is used for tests that are:
- **Slow**: They involve network latency.
- **Expensive**: They cost real money to run.
- **Non-deterministic**: Their output can vary slightly.
- **Dependent on external services**: They will fail if the API is down or keys are missing.

By marking these tests, we can easily exclude them for fast, local development runs.

### Which Tests Cost Money?

Any test decorated with `@pytest.mark.llm` is designed to make a real API call and will cost money. The example test `test_stream_new_message_service_with_real_claude_llm` explicitly calls an LLM service to test the end-to-end streaming functionality.

## Understanding the Coverage Report

The `--cov` flags generate reports that show how much of your code is exercised by the tests.

### Terminal Report (`term-missing`)

This option prints a summary table directly into your terminal after the tests finish.

```
Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
backend/__init__.py                     0      0   100%
backend/api/nodes.py                  148     27    82%   43-44, 65, 110-115, 130-131, 151-152...
...
-----------------------------------------------------------------
TOTAL                                1234    200    84%
```

- **Stmts**: Total number of executable statements.
- **Miss**: Number of statements not run by any test.
- **Cover**: The percentage of code covered (`(Stmts - Miss) / Stmts`).
- **Missing**: The specific line numbers or ranges that are **not covered by tests**. This is the most important column for improving coverage.

### HTML Report (`html`)

This option generates a detailed, interactive HTML report in a new `htmlcov/` directory.

**To view it, open the `htmlcov/index.html` file in your web browser.**

This report is incredibly useful because it lets you visually inspect your code. You can click on any file to see exactly which lines are:
- **Green**: Covered by tests.
- **Red**: Not covered by tests.
- **Grey**: Excluded (e.g., comments, `if __name__ == "__main__":`).

![Example of an HTML Coverage Report](https://i.stack.imgur.com/n1fV5.png)

## Advanced: Analyzing Missing Coverage with `annotate_coverage.py`

When you find a file with low coverage, the next step is to write tests for the "missing" lines. The `annotate_coverage.py` script is a powerful tool to help with this, especially when used with an LLM assistant.

### What This Script Does

The script takes a single line of output from the `term-missing` report and does the following:

1.  **Parses the line** to find the file path (e.g., `backend/api/nodes.py`) and the list of missing line numbers (e.g., `43-44, 65, 110-115, ...`).
2.  **Reads the original Python file**.
3.  **Creates a new, annotated file** with the suffix `.annotated.txt` (e.g., `nodes.py.annotated.txt`).
4.  In this new file, it **wraps the code** in `<covered>` and `<missing>` tags, making it crystal clear which parts of the code lack test coverage.

### Workflow: How to Use It with an LLM

Here is a step-by-step guide to improve test coverage for a specific file.

**Step 1: Get the Coverage Report**

Run the standard tests and look at the terminal report for a file you want to improve.

```bash
pytest -m "not llm" --cov=backend --cov-report=term-missing
```

Let's say you see this line in the output:

```
backend\api\nodes.py                  148     27    82%   43-44, 65, 110-115, 130-131, 151-152, 174-175, 187, 210-213, 240, 253-261
```

**Step 2: Run the Annotation Script**

Copy that entire line and pass it to the script as a single string argument. **Use quotes to ensure it's treated as one argument.**

```bash
python backend/scripts/annotate_coverage.py "backend\api\nodes.py                  148     27    82%   43-44, 65, 110-115, 130-131, 151-152, 174-175, 187, 210-213, 240, 253-261"
```

The script will create a file named `backend/api/nodes.py.annotated.txt`.

**Step 3: Use the Annotated File with an LLM**

This is where the magic happens. You now have the perfect context to ask an AI for help.

1.  **Open** the newly generated `backend/api/nodes.py.annotated.txt` file.
2.  **Copy** its entire content.
3.  **Paste** it into your favorite LLM (e.g., ChatGPT, Claude, Gemini).
4.  **Provide a clear prompt** asking it to write the missing tests.

**Example Prompt for the LLM:**

> Hello! Below is a Python file from my project, annotated with test coverage information. The code wrapped in `<missing>` tags is not currently covered by any tests. The code in `<covered>` tags is already tested.
>
> Please write new `pytest` tests that specifically target and cover the code inside the `<missing>` blocks. Make sure the new tests are clear, robust, and follow best practices for `pytest`.
>
> ```python
> <covered>
> # ... covered code from the file ...
> </covered>
> <missing>
> # ... missing code from the file ...
> </missing>
> <covered>
> # ... more covered code ...
> </covered>
> ```

The LLM can now easily identify the exact logic that needs testing and generate high-quality `pytest` functions for you to add to your test suite. This workflow dramatically speeds up the process of achieving high test coverage.