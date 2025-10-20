# Usage

This document provides detailed instructions on how to use the AI Test Agent.

## Commands

The AI Test Agent provides a command-line interface (CLI) for easy integration into your development workflow.

### Analyze a Project

This command analyzes the specified project directory, identifies the project structure, and saves the analysis to a JSON file.

```bash
ai-test-agent analyze --project-path /path/to/project --output analysis.json
```

**Arguments:**

*   `--project-path`: The path to the project you want to analyze.
*   `--output`: The path to the output JSON file where the analysis will be saved.

### Generate Tests

This command generates test files for the specified project and saves them in the `tests` directory.

```bash
ai-test-agent generate --project-path /path/to/project --output-dir tests
```

**Arguments:**

*   `--project-path`: The path to the project for which you want to generate tests.
*   `--output-dir`: The directory where the generated test files will be saved.

### Run Tests

This command executes the tests in the specified project and saves the results to a JSON file.

```bash
ai-test-agent run --project-path /path/to/project --output results.json
```

**Arguments:**

*   `--project-path`: The path to the project where the tests will be run.
*   `--output`: The path to the output JSON file where the test results will be saved.

### Generate Report

This command generates an HTML report from the test results.

```bash
ai-test-agent report --project-path /path/to/project --test-results results.json --output report.html
```

**Arguments:**

*   `--project-path`: The path to the project.
*   `--test-results`: The path to the JSON file containing the test results.
*   `--output`: The path to the output HTML report file.

### Run Complete Workflow

This command runs the entire workflow: analysis, test generation, execution, and reporting.

```bash
ai-test-agent all --project-path /path/to/project
```

**Arguments:**

*   `--project-path`: The path to the project.

### Interactive Mode

This command starts the agent in interactive mode, allowing you to run commands one by one.

```bash
ai-test-agent interactive --project-path /path/to/project
```

In interactive mode, you can type commands to the agent. For example:

```
You> analyze the project
Agent: Analyzing project...
You> generate tests
Agent: Generating tests...
You> run tests
Agent: Running tests...
You> generate report
Agent: Generating report...
```

To exit the interactive mode, type `exit` or `quit`.

## Configuration

The agent can be configured through environment variables or configuration files:

*   **`OLLAMA_HOST`**: Host for Ollama service
*   **`OLLAMA_PORT`**: Port for Ollama service
*   **`DEFAULT_MODEL`**: Default LLM model to use
