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

### Using Poetry

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

### Usage

## Analyze a Project
This command analyzes the specified project directory, identifies the project structure, and saves the analysis to a JSON file.
```bash
ai-test-agent analyze --project-path /path/to/project --output analysis.json
```

## Generate Tests
This command generates test files for the specified project and saves them in the `tests` directory.
```bash
ai-test-agent generate --project-path /path/to/project --output-dir tests
```

## Run Tests
This command executes the tests in the specified project and saves the results to a JSON file.
```bash
ai-test-agent run --project-path /path/to/project --output results.json
```

## Generate Report
This command generates an HTML report from the test results.
```bash
ai-test-agent report --project-path /path/to/project --test-results results.json --output report.html
```

## Run Complete Workflow
This command runs the entire workflow: analysis, test generation, execution, and reporting.
```bash
ai-test-agent all --project-path /path/to/project
```

## Interactive Mode
This command starts the agent in interactive mode, allowing you to run commands one by one.
```bash
ai-test-agent interactive --project-path /path/to/project
```

### Configuration
The agent can be configured through environment variables or configuration files:

 - **OLLAMA_HOST**: Host for Ollama service
 - **OLLAMA_PORT**: Port for Ollama service
 - **DEFAULT_MODEL**: Default LLM model to use

### Contributing
 - Fork the repository
 - Create a feature branch
 - Make your changes
 - Add tests
 - Submit a pull request


