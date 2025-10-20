# AI Test Agent

An AI-powered test automation agent that analyzes code, generates tests, and produces detailed reports.

## Features

- **Project Analysis**: Analyzes project structure and identifies components for testing
- **Test Generation**: Generates comprehensive tests for various programming languages
- **Test Execution**: Runs tests and collects results
- **Reporting**: Produces detailed test reports in multiple formats
- **Coverage Analysis**: Generates code coverage reports
- **CLI Interface**: Command-line interface for easy integration
- **Docker Support**: Containerized for easy deployment

## Supported Languages

- Python
- JavaScript/TypeScript
- Java

## Installation

### Option 1: Pip / Pipx (recommended)

Install the CLI globally so it is available from any project directory.

```bash
pipx install ai-test-agent
# or, if you are working from a checked-out repo
pipx install .
```

You can also install into an existing virtual environment:

```bash
pip install ai-test-agent
```

### Option 2: Using Poetry (development)

```bash
git clone https://github.com/yourusername/ai-test-agent.git
cd ai-test-agent
poetry install
```

## Using Docker
```bash
docker build -t ai-test-agent .
docker run -it ai-test-agent
```

## Quickstart Workflow

1. **Initialize your project**  
   From inside the project directory you want the agent to manage:
   ```bash
   ai-test-agent init
   ```
   This creates `.aitestagent/config.json` with sensible defaults (paths, thresholds, model names).  
   Rerun `init` at any time to regenerate or adjust the manifest.

2. **Analyze the codebase**  
   When inside an initialized project, you no longer need to repeat `--project-path`:
   ```bash
    ai-test-agent analyze
   ```
   Results are written to the configured analysis output path (defaults to `analysis.json`).

3. **Generate tests**
   ```bash
   ai-test-agent generate
   ```
   Tests are written to the configured tests directory (defaults to `tests/`).

4. **Execute tests**
   ```bash
   ai-test-agent run
   ```
   Test results and coverage thresholds respect the manifest configuration.

5. **Produce a report**
   ```bash
   ai-test-agent report
   ```

6. **Run everything end-to-end**
   ```bash
   ai-test-agent all
   ```

If you prefer to override any setting ad-hoc (e.g., a different output path), pass the flag and it will override the manifest for that invocation.

## Commands At a Glance

| Command | Description |
| ------- | ----------- |
| `ai-test-agent init` | Create `.aitestagent/config.json` in the current project. |
| `ai-test-agent analyze` | Parse the project and write the structural analysis. |
| `ai-test-agent generate` | Generate tests into the configured output directory. |
| `ai-test-agent run` | Execute tests, collect results, and enforce coverage thresholds. |
| `ai-test-agent report` | Build an HTML report from stored results. |
| `ai-test-agent all` | Run analyze → generate → run → report in one go. |
| `ai-test-agent debug` | Attempt iterative fixes when tests fail. |
| `ai-test-agent interactive` | (Placeholder) Future interactive workflow. |

From outside an initialized project, you can still supply paths explicitly, e.g.:
```bash
ai-test-agent analyze --project-path /path/to/project
```

For a detailed option reference, see [`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md).

## Project Manifest

The manifest created by `init` lives at `.aitestagent/config.json` and stores relative paths
and defaults for:

- project root
- tests/analysis/results/report output paths
- coverage thresholds
- default LLM model

Feel free to edit this file directly or rerun `ai-test-agent init` to regenerate it.  
All commands look for the manifest in the current directory or any parent directory.

## Configuration

Additional runtime settings can be provided via environment variables (particularly for LLM access):

 - **OLLAMA_HOST**: Host for Ollama service
 - **OLLAMA_PORT**: Port for Ollama service
 - **DEFAULT_MODEL**: Default LLM model to use

The CLI will also create `.aitestagent/.env.example` during `init` for convenience.

### Contributing
 - Fork the repository
 - Create a feature branch
 - Make your changes
 - Add tests
 - Submit a pull request
