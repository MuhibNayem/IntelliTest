import json
import click
from rich.progress import Progress, SpinnerColumn, TextColumn
from pathlib import Path
import asyncio

from .agent.agent import TestAutomationAgent
from .config import settings


@click.group()
def main():
    """AI Test Agent CLI: Automate test generation, execution, and reporting using AI.

    This command-line interface allows you to analyze your project, generate tests,
    run them, and view comprehensive reports. You can also interact with the AI agent
    in an interactive mode.
    """
    pass


@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project to analyze. Defaults to the current working directory.')
@click.option('--output', default=str(settings.analysis_output_file), help='Path to the output JSON file where analysis results will be saved.')
@click.option('--llm-model', default=settings.llm_model_name, help='Specify the LLM model to use for analysis (if applicable).')
def analyze(project_path: str, output: str, llm_model: str):
    """
    Analyze a project's structure, code, and identify business logic.

    This command scans the specified project path, parses code files (Python, JavaScript, Java),
    builds dependency and call graphs, and identifies key business logic components.
    The detailed analysis is then saved to a JSON file.
    """

    current_settings = settings.model_copy(update={
        "project_root": Path(project_path),
        "analysis_output_file": Path(output),
        "llm_model_name": llm_model,
    })

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Analyzing project...", total=1)
        agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=current_settings)
        result = agent.analyze_project()
        progress.update(task, completed=1)

    if result["success"]:
        with open(output, "w") as f:
            json.dump(result["analysis"], f, indent=2)
        click.echo(f"Analysis complete. Results saved to {output}")
    else:
        click.echo(f"Error: {result['error']}")



@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project for which to generate tests. Defaults to the current working directory.')
@click.option('--output-dir', default=str(settings.tests_output_dir), help='Directory where the generated test files will be saved.')
@click.option('--llm-model', default=settings.llm_model_name, help='Specify the LLM model to use for test generation.')
def generate(project_path: str, output_dir: str, llm_model: str):
    """
    Generate AI-powered test cases for a project based on its analysis.

    This command uses the project analysis (from the 'analyze' command) and an LLM
    to create relevant and diverse test cases (positive, negative, edge) for identified
    business logic components. The generated tests are saved to the specified output directory.
    """

    current_settings = settings.model_copy(update={
        "project_root": Path(project_path),
        "tests_output_dir": Path(output_dir),
        "llm_model_name": llm_model,
    })

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Generating tests...", total=1)
        agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=current_settings)
        result = agent.generate_tests(output_dir)
        progress.update(task, completed=1)

    if result["success"]:
        click.echo(f"Tests generated successfully in {result['tests']['output_dir']}")
        for source_file, test_file in result["tests"]["generated_tests"].items():
            click.echo(f"  {source_file} -> {test_file}")
    else:
        click.echo(f"Error: {result['error']}")


@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project to run tests for. Defaults to the current working directory.')
@click.option('--output', default=str(settings.results_output_file), help='Path to the output JSON file where test results will be saved.')
@click.option('--llm-model', default=settings.llm_model_name, help='Specify the LLM model to use for test execution (if applicable).')
@click.option('--min-line-coverage', type=float, default=settings.min_line_coverage, help='Minimum required line coverage percentage.')
@click.option('--min-branch-coverage', type=float, default=settings.min_branch_coverage, help='Minimum required branch coverage percentage.')
@click.option('--min-function-coverage', type=float, default=settings.min_function_coverage, help='Minimum required function coverage percentage.')
def run(project_path: str, output: str, llm_model: str, min_line_coverage: float, min_branch_coverage: float, min_function_coverage: float):
    """
    Execute generated tests for a project and collect results.

    This command automatically detects the test framework (e.g., pytest, Jest, JUnit)
    and runs the tests found in the project. It collects detailed results,
    including code coverage, and saves them to a JSON file.
    """

    current_settings = settings.model_copy(update={
        "project_root": Path(project_path),
        "results_output_file": Path(output),
        "llm_model_name": llm_model,
        "min_line_coverage": min_line_coverage,
        "min_branch_coverage": min_branch_coverage,
        "min_function_coverage": min_function_coverage,
    })

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Running tests...", total=1)
        agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=current_settings)
        result = agent.run_tests()
        progress.update(task, completed=1)

    if result["success"]:
        with open(output, "w") as f:
            json.dump(result["results"], f, indent=2)
        click.echo(f"Tests completed. Results saved to {output}")
        summary = result["results"].get("summary", {})
        click.echo(
            f"Summary: {summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed, {summary.get('skipped', 0)} skipped"
        )
    else:
        click.echo(f"Error: {result['error']}")


@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project associated with the test results. Defaults to the current working directory.')
@click.option('--test-results', required=True, type=click.Path(exists=True), help='Path to the JSON file containing the test results (e.g., output from the "run" command).')
@click.option('--output', default=str(settings.report_output_file), help='Path to the output HTML report file.')
@click.option('--llm-model', default=settings.llm_model_name, help='Specify the LLM model to use for reporting (if applicable).')
def report(project_path: str, test_results: str, output: str, llm_model: str):
    """
    Generate a human-readable report from collected test results.

    This command takes a JSON file containing test results (typically generated by the 'run' command)
    and produces a formatted report, such as an HTML report, for easy review.
    """

    current_settings = settings.model_copy(update={
        "project_root": Path(project_path),
        "report_output_file": Path(output),
        "llm_model_name": llm_model,
    })

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Generating report...", total=1)
        agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=current_settings)

        with open(test_results, "r") as f:
            results = json.load(f)

        # Try to locate a bundled HTML template; if not found, pass an empty string
        # so the reporter can decide on a default behavior.
        template_path = Path(__file__).resolve().parent / "templates" / "report_template.html"
        template_arg = str(template_path) if template_path.exists() else ""

        report_path = agent.results_aggregator.reporter.generate_html_report(
            results, output, template_arg
        )
        progress.update(task, completed=1)
    click.echo(f"Report generated: {report_path}")


@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project to run the full workflow on. Defaults to the current working directory.')
@click.option('--llm-model', default=settings.llm_model_name, help='Specify the LLM model to use for all AI-driven tasks.')
@click.option('--tests-output-dir', default=str(settings.tests_output_dir), help='Directory where generated test files will be saved.')
@click.option('--analysis-output-file', default=str(settings.analysis_output_file), help='Path to the output JSON file for project analysis.')
@click.option('--results-output-file', default=str(settings.results_output_file), help='Path to the output JSON file for test results.')
@click.option('--report-output-file', default=str(settings.report_output_file), help='Path to the output HTML report file.')
@click.option('--min-line-coverage', type=float, default=settings.min_line_coverage, help='Minimum required line coverage percentage.')
@click.option('--min-branch-coverage', type=float, default=settings.min_branch_coverage, help='Minimum required branch coverage percentage.')
@click.option('--min-function-coverage', type=float, default=settings.min_function_coverage, help='Minimum required function coverage percentage.')
@click.option('--debug-on-fail', is_flag=True, help='If set, the agent will attempt to debug and fix failed tests iteratively.')
@click.option('--debug-max-iterations', type=int, default=3, help='Maximum number of debugging iterations if --debug-on-fail is enabled.')
def all(
    project_path: str,
    llm_model: str,
    tests_output_dir: str,
    analysis_output_file: str,
    results_output_file: str,
    report_output_file: str,
    min_line_coverage: float,
    min_branch_coverage: float,
    min_function_coverage: float,
    debug_on_fail: bool,
    debug_max_iterations: int
):
    """
    Run the complete test automation workflow: analyze, generate, run, and report.

    This command orchestrates the entire process from project analysis and AI-driven
    test generation to test execution and final report generation. It's a convenient
    way to get a full overview of your project's test status.
    """

    current_settings = settings.model_copy(update={
        "project_root": Path(project_path),
        "llm_model_name": llm_model,
        "tests_output_dir": Path(tests_output_dir),
        "analysis_output_file": Path(analysis_output_file),
        "results_output_file": Path(results_output_file),
        "report_output_file": Path(report_output_file),
        "min_line_coverage": min_line_coverage,
        "min_branch_coverage": min_branch_coverage,
        "min_function_coverage": min_function_coverage,
    })
    
    print(f"Starting full test automation workflow for project at {Path(project_path)}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=current_settings)

        # Step 1: Analyze project
        analyze_task = progress.add_task("[cyan]Step 1: Analyzing project...", total=1)
        analysis_result = agent.analyze_project()
        
        progress.update(analyze_task, completed=1)
        if not analysis_result["success"]:
            click.echo(f"Error in project analysis: {analysis_result['error']}")
            return

        # Step 2: Generate tests
        generate_task = progress.add_task("[cyan]Step 2: Generating tests...", total=1)
        test_result = agent.generate_tests(str(current_settings.tests_output_dir))
        progress.update(generate_task, completed=1)
        click.echo(f"Generated {len(test_result['tests'].get('generated_tests', {}))} test files.")
        click.echo(f"Tests are : {test_result['tests'].get('generated_tests', 'N/A')}")
        if not test_result["success"]:
            click.echo(f"Error in test generation: {test_result['error']}")
            return
        generated_tests = test_result["tests"].get("generated_tests", {})
        if not generated_tests:
            click.echo("No tests were generated; skipping test execution and report generation.")
            return

        # Step 3: Run tests
        run_task = progress.add_task("[cyan]Step 3: Running tests...", total=1)
        run_result = agent.run_tests() # run_tests handles async internally
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
                    run_result = debug_result["results"] # Update run_result with debugged results
                else:
                    click.echo(f"Debugging failed: {debug_result['error']}")
                
                if "history" in debug_result and debug_result["history"]:
                    click.echo("\n--- Debugging History (from 'all' command) ---")
                    for entry in debug_result["history"]:
                        click.echo(f"Iteration {entry['iteration']}: Status - {entry['status']}")
                        if entry['status'] == "fix_attempt":
                            click.echo(f"  AI Reasoning: {entry['fix_result'].get('reasoning', 'N/A')}")
                            for fix in entry['fix_result'].get('fixes_applied', []):
                                click.echo(f"    Applied Fix to {fix.get('file_to_modify')}: {fix.get('modification_type')}")
                        elif entry['status'] == "error":
                            click.echo(f"  Error: {entry['message']}")

                if not debug_result["success"]:
                    return # Exit if debugging failed
            else:
                return # Exit if tests failed and no debugging requested

        # Step 4: Generate report
        report_task = progress.add_task("[cyan]Step 4: Generating report...", total=1)
        report_result = agent.generate_report(run_result["results"], str(current_settings.report_output_file))
        progress.update(report_task, completed=1)
        if not report_result["success"]:
            click.echo(f"Error in report generation: {report_result['error']}")
            return

    click.echo("Test automation workflow completed successfully!")
    click.echo(f"Tests generated in: {test_result['tests']['output_dir']}")
    click.echo(f"Report generated: {report_result['report_path']}")


@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project to debug. Defaults to the current working directory.')
@click.option('--llm-model', default=settings.llm_model_name, help='Specify the LLM model to use for debugging.')
@click.option('--max-iterations', type=int, default=3, help='Maximum number of debugging iterations.')
def debug(project_path: str, llm_model: str, max_iterations: int):
    """
    Initiate AI-driven iterative debugging for failed tests.

    This command runs tests, and if failures are detected, the AI agent will attempt
    to analyze the failures and suggest/apply fixes, re-running tests until they pass
    or the maximum number of iterations is reached.
    """
    current_settings = settings.model_copy(update={
        "project_root": Path(project_path),
        "llm_model_name": llm_model,
    })

    agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=current_settings)
    import asyncio
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
            if entry['status'] == "fix_attempt":
                click.echo(f"  AI Reasoning: {entry['fix_result'].get('reasoning', 'N/A')}")
                for fix in entry['fix_result'].get('fixes_applied', []):
                    click.echo(f"    Applied Fix to {fix.get('file_to_modify')}: {fix.get('modification_type')}")
            elif entry['status'] == "error":
                click.echo(f"  Error: {entry['message']}")


@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project context for the interactive session. Defaults to the current working directory.')
@click.option('--llm-model', default=settings.llm_model_name, help='Specify the LLM model to use for the interactive session.')
def interactive(project_path: str, llm_model: str):
    """
    Start an interactive session with the AI Test Agent.

    In this mode, you can chat directly with the AI agent, providing natural language
    commands or questions. The agent will use its tools to respond and perform tasks.
    Type 'exit' or 'quit' to end the session.
    """
    click.echo("Starting interactive session...")
    click.echo("Type 'exit' to quit.")

    current_settings = settings.model_copy(update={
        "project_root": Path(project_path),
        "llm_model_name": llm_model,
    })

    agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=current_settings)

    while True:
        user_input = click.prompt("\nYou>")
        if user_input.lower() in ["exit", "quit"]:
            break

        result_dict = agent.run(user_input)
        if result_dict["success"]:
            click.echo(f"Agent: {result_dict['result']}")
        else:
            click.echo(f"Error: {result_dict['error']}")
            
            
