import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import click
from rich.progress import Progress, SpinnerColumn, TextColumn

from .agent.agent import TestAutomationAgent
from .config import Settings, settings

CONFIG_DIR_NAME = ".aitestagent"
CONFIG_FILE_NAME = "config.json"


def _default_manifest_template() -> Dict[str, Any]:
    return {
        "project_root": ".",
        "tests_output_dir": str(settings.tests_output_dir),
        "analysis_output_file": str(settings.analysis_output_file),
        "results_output_file": str(settings.results_output_file),
        "report_output_file": str(settings.report_output_file),
        "xml_report_output_file": str(settings.xml_report_output_file),
        "coverage_output_file": str(settings.coverage_output_file),
        "llm_model_name": settings.llm_model_name,
        "min_line_coverage": settings.min_line_coverage,
        "min_branch_coverage": settings.min_branch_coverage,
        "min_function_coverage": settings.min_function_coverage,
    }


def _find_manifest(start: Path) -> Optional[Path]:
    for candidate_root in [start, *start.parents]:
        manifest = candidate_root / CONFIG_DIR_NAME / CONFIG_FILE_NAME
        if manifest.exists():
            return manifest
    return None


def _load_manifest_data(manifest_path: Path) -> Dict[str, Any]:
    try:
        return json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Malformed manifest at {manifest_path}: {exc}") from exc


def _ensure_path(value: Any, project_root: Path) -> Path:
    path_value = Path(value)
    if not path_value.is_absolute():
        path_value = project_root / path_value
    return path_value.resolve()


def resolve_project_context(
    project_path_arg: Optional[str],
    overrides: Dict[str, Optional[Any]],
) -> Tuple[Settings, Path, Optional[Path]]:
    start = Path(project_path_arg).expanduser().resolve() if project_path_arg else Path.cwd()
    manifest_path = _find_manifest(start)
    manifest_data: Dict[str, Any] = {}
    manifest_root: Optional[Path] = None

    if manifest_path:
        manifest_data = _load_manifest_data(manifest_path)
        manifest_root = manifest_path.parent.parent

    project_root = Path(project_path_arg).expanduser().resolve() if project_path_arg else (
        manifest_root if manifest_root else start
    )
    if not project_root.exists():
        raise click.ClickException(f"Project path '{project_root}' does not exist.")

    combined = _default_manifest_template()
    combined.update(manifest_data)
    for key, value in overrides.items():
        if value is not None:
            combined[key] = value

    update = {
        "project_root": project_root,
        "tests_output_dir": _ensure_path(combined["tests_output_dir"], project_root),
        "analysis_output_file": _ensure_path(combined["analysis_output_file"], project_root),
        "results_output_file": _ensure_path(combined["results_output_file"], project_root),
        "report_output_file": _ensure_path(combined["report_output_file"], project_root),
        "xml_report_output_file": _ensure_path(combined["xml_report_output_file"], project_root),
        "coverage_output_file": _ensure_path(combined["coverage_output_file"], project_root),
        "llm_model_name": combined["llm_model_name"],
        "min_line_coverage": float(combined["min_line_coverage"]),
        "min_branch_coverage": float(combined["min_branch_coverage"]),
        "min_function_coverage": float(combined["min_function_coverage"]),
    }

    current_settings = settings.model_copy(update=update)
    return current_settings, project_root, manifest_path


def _write_manifest(project_root: Path, manifest: Dict[str, Any], force: bool) -> Path:
    manifest_dir = project_root / CONFIG_DIR_NAME
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / CONFIG_FILE_NAME

    if manifest_path.exists() and not force:
        if not click.confirm(
            f"A manifest already exists at {manifest_path}. Overwrite?", default=False
        ):
            raise click.Abort()

    manifest_to_write = manifest.copy()
    manifest_to_write["project_root"] = "."
    manifest_path.write_text(json.dumps(manifest_to_write, indent=2))

    env_example = manifest_dir / ".env.example"
    if not env_example.exists():
        env_example.write_text("OPENAI_API_KEY=\n")

    return manifest_path


@click.group()
def main():
    """AI Test Agent CLI: Automate test generation, execution, and reporting using AI."""
    pass


@main.command()
@click.option(
    "--project-path",
    type=click.Path(file_okay=False, dir_okay=True),
    default=".",
    help="Project directory to initialize. Defaults to the current working directory.",
)
@click.option("--tests-output-dir", default=None, help="Relative path for generated tests.")
@click.option("--analysis-output-file", default=None, help="Relative path for analysis JSON.")
@click.option("--results-output-file", default=None, help="Relative path for test results JSON.")
@click.option("--report-output-file", default=None, help="Relative path for HTML report.")
@click.option("--llm-model", default=None, help="Default LLM model for this project.")
@click.option("--force", is_flag=True, help="Overwrite existing configuration without prompting.")
def init(
    project_path: str,
    tests_output_dir: Optional[str],
    analysis_output_file: Optional[str],
    results_output_file: Optional[str],
    report_output_file: Optional[str],
    llm_model: Optional[str],
    force: bool,
):
    """Create a local configuration manifest for the current project."""
    project_root = Path(project_path).expanduser().resolve()
    project_root.mkdir(parents=True, exist_ok=True)

    manifest = _default_manifest_template()
    if tests_output_dir is not None:
        manifest["tests_output_dir"] = tests_output_dir
    if analysis_output_file is not None:
        manifest["analysis_output_file"] = analysis_output_file
    if results_output_file is not None:
        manifest["results_output_file"] = results_output_file
    if report_output_file is not None:
        manifest["report_output_file"] = report_output_file
    if llm_model is not None:
        manifest["llm_model_name"] = llm_model

    manifest_path = _write_manifest(project_root, manifest, force=force)
    click.echo(f"Initialized AI Test Agent configuration at {manifest_path}")


@main.command()
@click.option(
    "--project-path",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Path to the project to analyze. Defaults to the current directory or manifest project root.",
)
@click.option("--output", default=None, help="Override output JSON file for analysis results.")
@click.option("--llm-model", default=None, help="Override the LLM model for this run.")
def analyze(project_path: Optional[str], output: Optional[str], llm_model: Optional[str]):
    """Analyze a project's structure, code, and identify business logic."""
    current_settings, project_root, _ = resolve_project_context(
        project_path,
        {
            "analysis_output_file": output,
            "llm_model_name": llm_model,
        },
    )
    output_path = current_settings.analysis_output_file

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("[cyan]Analyzing project...", total=1)
        agent = TestAutomationAgent(project_path=project_root, settings_obj=current_settings)
        result = agent.analyze_project()
        progress.update(task, completed=1)

    if result["success"]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result["analysis"], indent=2))
        click.echo(f"Analysis complete. Results saved to {output_path}")
    else:
        click.echo(f"Error: {result['error']}")


@main.command()
@click.option(
    "--project-path",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Path to the project for which to generate tests. Defaults to the manifest project root.",
)
@click.option("--output-dir", default=None, help="Directory where generated tests will be saved.")
@click.option("--llm-model", default=None, help="Override the LLM model for test generation.")
def generate(project_path: Optional[str], output_dir: Optional[str], llm_model: Optional[str]):
    """Generate AI-powered test cases for a project based on its analysis."""
    current_settings, project_root, _ = resolve_project_context(
        project_path,
        {
            "tests_output_dir": output_dir,
            "llm_model_name": llm_model,
        },
    )
    tests_dir = current_settings.tests_output_dir

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("[cyan]Generating tests...", total=1)
        agent = TestAutomationAgent(project_path=project_root, settings_obj=current_settings)
        result = agent.generate_tests(str(tests_dir))
        progress.update(task, completed=1)

    if result["success"]:
        click.echo(f"Tests generated successfully in {tests_dir}")
        for source_file, test_file in result["tests"]["generated_tests"].items():
            click.echo(f"  {source_file} -> {test_file}")
    else:
        click.echo(f"Error: {result['error']}")


@main.command()
@click.option(
    "--project-path",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Path to the project to run tests for. Defaults to the manifest project root.",
)
@click.option("--output", default=None, help="Override the output JSON file for test results.")
@click.option("--llm-model", default=None, help="Override the LLM model for test execution.")
@click.option("--min-line-coverage", type=float, default=None, help="Minimum required line coverage percentage.")
@click.option("--min-branch-coverage", type=float, default=None, help="Minimum required branch coverage percentage.")
@click.option("--min-function-coverage", type=float, default=None, help="Minimum required function coverage percentage.")
def run(
    project_path: Optional[str],
    output: Optional[str],
    llm_model: Optional[str],
    min_line_coverage: Optional[float],
    min_branch_coverage: Optional[float],
    min_function_coverage: Optional[float],
):
    """Execute generated tests for a project and collect results."""
    current_settings, project_root, _ = resolve_project_context(
        project_path,
        {
            "results_output_file": output,
            "llm_model_name": llm_model,
            "min_line_coverage": min_line_coverage,
            "min_branch_coverage": min_branch_coverage,
            "min_function_coverage": min_function_coverage,
        },
    )
    output_path = current_settings.results_output_file

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("[cyan]Running tests...", total=1)
        agent = TestAutomationAgent(project_path=project_root, settings_obj=current_settings)
        result = agent.run_tests()
        progress.update(task, completed=1)

    if result["success"]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result["results"], indent=2))
        click.echo(f"Tests completed. Results saved to {output_path}")
        summary = result["results"].get("summary", {})
        click.echo(
            f"Summary: {summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed, {summary.get('skipped', 0)} skipped"
        )
    else:
        click.echo(f"Error: {result['error']}")


@main.command()
@click.option(
    "--project-path",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Path to the project associated with the test results. Defaults to the manifest project root.",
)
@click.option("--test-results", default=None, help="Path to the JSON file containing test results.")
@click.option("--output", default=None, help="Override the output HTML report file.")
@click.option("--llm-model", default=None, help="Override the LLM model for reporting.")
def report(
    project_path: Optional[str],
    test_results: Optional[str],
    output: Optional[str],
    llm_model: Optional[str],
):
    """Generate a human-readable report from collected test results."""
    current_settings, project_root, _ = resolve_project_context(
        project_path,
        {
            "report_output_file": output,
            "llm_model_name": llm_model,
        },
    )
    report_path = current_settings.report_output_file
    test_results_path = (
        _ensure_path(test_results, current_settings.project_root)
        if test_results is not None
        else current_settings.results_output_file
    )

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("[cyan]Generating report...", total=1)
        agent = TestAutomationAgent(project_path=project_root, settings_obj=current_settings)

        results = json.loads(test_results_path.read_text())
        template_path = Path(__file__).resolve().parent / "templates" / "report_template.html"
        template_arg = str(template_path) if template_path.exists() else ""

        generated_path = agent.results_aggregator.reporter.generate_html_report(
            results,
            str(report_path),
            template_arg,
        )
        progress.update(task, completed=1)
    click.echo(f"Report generated: {generated_path}")


@main.command()
@click.option(
    "--project-path",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Path to the project to run the full workflow on. Defaults to the manifest project root.",
)
@click.option("--llm-model", default=None, help="Override the LLM model for this workflow.")
@click.option("--tests-output-dir", default=None, help="Override tests output directory.")
@click.option("--analysis-output-file", default=None, help="Override analysis output file.")
@click.option("--results-output-file", default=None, help="Override results output file.")
@click.option("--report-output-file", default=None, help="Override HTML report output file.")
@click.option("--min-line-coverage", type=float, default=None, help="Minimum required line coverage percentage.")
@click.option("--min-branch-coverage", type=float, default=None, help="Minimum required branch coverage percentage.")
@click.option("--min-function-coverage", type=float, default=None, help="Minimum required function coverage percentage.")
@click.option("--debug-on-fail", is_flag=True, help="If set, the agent will attempt to debug failed tests.")
@click.option("--debug-max-iterations", type=int, default=3, help="Maximum number of debugging iterations.")
def all(
    project_path: Optional[str],
    llm_model: Optional[str],
    tests_output_dir: Optional[str],
    analysis_output_file: Optional[str],
    results_output_file: Optional[str],
    report_output_file: Optional[str],
    min_line_coverage: Optional[float],
    min_branch_coverage: Optional[float],
    min_function_coverage: Optional[float],
    debug_on_fail: bool,
    debug_max_iterations: int,
):
    """Run the complete test automation workflow: analyze, generate, run, and report."""
    current_settings, project_root, _ = resolve_project_context(
        project_path,
        {
            "llm_model_name": llm_model,
            "tests_output_dir": tests_output_dir,
            "analysis_output_file": analysis_output_file,
            "results_output_file": results_output_file,
            "report_output_file": report_output_file,
            "min_line_coverage": min_line_coverage,
            "min_branch_coverage": min_branch_coverage,
            "min_function_coverage": min_function_coverage,
        },
    )

    tests_dir = current_settings.tests_output_dir
    analysis_path = current_settings.analysis_output_file
    results_path = current_settings.results_output_file
    report_path = current_settings.report_output_file

    click.echo(f"Starting full test automation workflow for project at {project_root}\n")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        agent = TestAutomationAgent(project_path=project_root, settings_obj=current_settings)

        analyze_task = progress.add_task("[cyan]Step 1: Analyzing project...", total=1)
        analysis_result = agent.analyze_project()
        progress.update(analyze_task, completed=1)
        if not analysis_result["success"]:
            click.echo(f"Error in project analysis: {analysis_result['error']}")
            return
        analysis_path.parent.mkdir(parents=True, exist_ok=True)
        analysis_path.write_text(json.dumps(analysis_result["analysis"], indent=2))

        generate_task = progress.add_task("[cyan]Step 2: Generating tests...", total=1)
        test_result = agent.generate_tests(str(tests_dir))
        progress.update(generate_task, completed=1)
        if not test_result["success"]:
            click.echo(f"Error in test generation: {test_result['error']}")
            return
        generated_tests = test_result["tests"].get("generated_tests", {})
        if not generated_tests:
            click.echo("No tests were generated; skipping execution and report generation.")
            return

        run_task = progress.add_task("[cyan]Step 3: Running tests...", total=1)
        run_result = agent.run_tests()
        progress.update(run_task, completed=1)

        if not run_result["success"] or run_result.get("results", {}).get("summary", {}).get("failed", 0) > 0:
            click.echo(f"Test execution failed: {run_result['error'] if not run_result['success'] else 'Some tests failed.'}")
            if debug_on_fail:
                click.echo("Initiating AI-driven debugging...")
                debug_task = progress.add_task("[yellow]Step 3.5: Debugging failed tests...", total=1)
                debug_result = asyncio.run(agent.debug_tests(max_iterations=debug_max_iterations))
                progress.update(debug_task, completed=1)
                if debug_result["success"]:
                    click.echo("Debugging completed successfully. All tests passed.")
                    run_result = {"results": debug_result["results"], "success": True}
                else:
                    click.echo(f"Debugging failed: {debug_result['error']}")
                    return
            else:
                return

        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(json.dumps(run_result["results"], indent=2))

        report_task = progress.add_task("[cyan]Step 4: Generating report...", total=1)
        report_result = agent.generate_report(run_result["results"], str(report_path))
        progress.update(report_task, completed=1)
        if not report_result["success"]:
            click.echo(f"Error in report generation: {report_result['error']}")
            return

    click.echo("Test automation workflow completed successfully!")
    click.echo(f"Tests generated in: {tests_dir}")
    click.echo(f"Results saved to: {results_path}")
    click.echo(f"Report generated: {report_result['report_path']}")


@main.command()
@click.option(
    "--project-path",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Path to the project to debug. Defaults to the manifest project root.",
)
@click.option("--llm-model", default=None, help="Override the LLM model for debugging.")
@click.option("--max-iterations", type=int, default=3, help="Maximum number of debugging iterations.")
def debug(project_path: Optional[str], llm_model: Optional[str], max_iterations: int):
    """Initiate AI-driven iterative debugging for failed tests."""
    current_settings, project_root, _ = resolve_project_context(
        project_path,
        {"llm_model_name": llm_model},
    )
    agent = TestAutomationAgent(project_path=project_root, settings_obj=current_settings)
    debug_result = asyncio.run(agent.debug_tests(max_iterations=max_iterations))

    if debug_result["success"]:
        click.echo("Debugging completed successfully!")
    else:
        click.echo(f"Debugging finished with errors: {debug_result['error']}")
        if "results" in debug_result:
            summary = debug_result["results"].get("summary", {})
            click.echo(
                f"Summary: {summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed, {summary.get('skipped', 0)} skipped"
            )

    if "history" in debug_result and debug_result["history"]:
        click.echo("\n--- Debugging History ---")
        for entry in debug_result["history"]:
            click.echo(f"Iteration {entry['iteration']}: Status - {entry['status']}")
            if entry["status"] == "fix_attempt":
                click.echo(f"  AI Reasoning: {entry['fix_result'].get('reasoning', 'N/A')}")
                for fix in entry["fix_result"].get("fixes_applied", []):
                    click.echo(f"    Applied Fix to {fix.get('file_to_modify')}: {fix.get('modification_type')}")
            elif entry["status"] == "error":
                click.echo(f"  Error: {entry['message']}")


@main.command()
@click.option(
    "--project-path",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Path to the project context for the interactive session. Defaults to the manifest project root.",
)
@click.option("--llm-model", default=None, help="Override the LLM model for the interactive session.")
def interactive(project_path: Optional[str], llm_model: Optional[str]):
    """Start an interactive session with the AI Test Agent."""
    current_settings, project_root, _ = resolve_project_context(
        project_path,
        {"llm_model_name": llm_model},
    )
    agent = TestAutomationAgent(project_path=project_root, settings_obj=current_settings)

    click.echo("Interactive mode not implemented yet. Stay tuned!")
