# AI Test Agent CLI Reference

The CLI can be installed globally (`pipx install ai-test-agent`) or inside a local virtual environment.  
After installation, run `ai-test-agent init` inside a project directory to create `.aitestagent/config.json`.  
All commands automatically read this manifest; pass flags to override values ad hoc.

| Command | Description | Key Options |
| ------- | ----------- | ----------- |
| `ai-test-agent init` | Scaffold `.aitestagent/config.json` in the current directory. | `--tests-output-dir`, `--analysis-output-file`, `--results-output-file`, `--report-output-file`, `--llm-model`, `--force` |
| `ai-test-agent analyze` | Parse the project and write analysis output. | `--project-path`, `--output`, `--llm-model` |
| `ai-test-agent generate` | Generate tests based on the latest analysis. | `--project-path`, `--output-dir`, `--llm-model` |
| `ai-test-agent run` | Execute tests, enforce coverage thresholds, and save results. | `--project-path`, `--output`, `--llm-model`, `--min-line-coverage`, `--min-branch-coverage`, `--min-function-coverage` |
| `ai-test-agent report` | Produce an HTML report from stored results. | `--project-path`, `--test-results`, `--output`, `--llm-model` |
| `ai-test-agent all` | Perform analyze → generate → run → report sequentially. | Supports all overrides from the individual commands plus `--debug-on-fail`, `--debug-max-iterations`. |
| `ai-test-agent debug` | Attempt iterative fixes for failing tests. | `--project-path`, `--llm-model`, `--max-iterations` |
| `ai-test-agent interactive` | Placeholder for future interactive workflows. | `--project-path`, `--llm-model` |

## Configuration Search Rules

1. Commands look for `.aitestagent/config.json` in the current directory or any parent directory.
2. If a manifest is found, relative paths in the file are resolved against the project root.
3. CLI flags override manifest values for the duration of that command invocation.
4. Without a manifest, commands fall back to explicit `--project-path` arguments or the current working directory.

## Manifest Fields

```jsonc
{
  "project_root": ".",
  "tests_output_dir": "tests",
  "analysis_output_file": "analysis.json",
  "results_output_file": "results.json",
  "report_output_file": "test_report.html",
  "xml_report_output_file": "test_report.xml",
  "coverage_output_file": "coverage_report.html",
  "llm_model_name": "qwen2.5-coder:1.5b",
  "min_line_coverage": 80.0,
  "min_branch_coverage": 80.0,
  "min_function_coverage": 80.0
}
```

Adjust paths or thresholds as needed. Values can be absolute or relative to the project root.

## Environment Variables

| Variable | Purpose |
| -------- | ------- |
| `OLLAMA_HOST` | Hostname for the Ollama server. |
| `OLLAMA_PORT` | Port for the Ollama server. |
| `DEFAULT_MODEL` | Override the default LLM model name. |

The `ai-test-agent init` command creates `.aitestagent/.env.example` to help teams track required variables.
