import click

from .agent.agent import TestAutomationAgent
from .config import settings


@click.group()
def main():
    """AI Test Agent CLI"""
    pass


@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project to analyze.')
@click.option('--output', default=str(settings.analysis_output_file), help='Path to the output JSON file.')
def analyze(project_path: str, output: str):
    """
    Analyze a project and save the analysis to a JSON file.
    """
    click.echo(f"Analyzing project at {project_path}...")
    agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=settings)
    result = agent.analyze_project()

    if result["success"]:
        with open(output, "w") as f:
            json.dump(result["analysis"], f, indent=2)
        click.echo(f"Analysis complete. Results saved to {output}")
    else:
        click.echo(f"Error: {result['error']}")


@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project.')
@click.option('--output-dir', default=str(settings.tests_output_dir), help='Directory to save generated tests.')
def generate(project_path: str, output_dir: str):
    """
    Generate tests for a project.
    """
    click.echo(f"Generating tests for project at {project_path}...")
    agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=settings)
    result = agent.generate_tests(output_dir)

    if result["success"]:
        click.echo(f"Tests generated successfully in {result['tests']['output_dir']}")
        for source_file, test_file in result["tests"]["generated_tests"].items():
            click.echo(f"  {source_file} -> {test_file}")
    else:
        click.echo(f"Error: {result['error']}")


@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project.')
@click.option('--output', default=str(settings.results_output_file), help='Path to the output JSON file.')
def run(project_path: str, output: str):
    """
    Run tests for a project.
    """
    click.echo("Running tests...")
    agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=settings)
    result = agent.run_tests()

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
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project.')
@click.option('--test-results', required=True, type=click.Path(exists=True), help='Path to the test results JSON file.')
@click.option('--output', default=str(settings.report_output_file), help='Path to the output HTML report file.')
def report(project_path: str, test_results: str, output: str):
    """
    Generate a report from test results.
    """
    click.echo("Generating report...")
    agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=settings)

    with open(test_results, "r") as f:
        results = json.load(f)

    report_path = agent.results_aggregator.reporter.generate_html_report(
        results, output
    )
    click.echo(f"Report generated: {report_path}")


@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project.')
def all(project_path: str):
    """
    Run the complete workflow (analyze, generate, run, and report).
    """
    click.echo(f"Running complete test automation workflow for project at {project_path}...")
    agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=settings)

    # Step 1: Analyze project
    click.echo("Step 1: Analyzing project...")
    analysis_result = agent.analyze_project()
    if not analysis_result["success"]:
        click.echo(f"Error in project analysis: {analysis_result['error']}")
        return

    # Step 2: Generate tests
    click.echo("Step 2: Generating tests...")
    test_result = agent.generate_tests(str(settings.tests_output_dir))
    if not test_result["success"]:
        click.echo(f"Error in test generation: {test_result['error']}")
        return

    # Step 3: Run tests
    click.echo("Step 3: Running tests...")
    run_result = agent.run_tests()
    if not run_result["success"]:
        click.echo(f"Error in test execution: {run_result['error']}")
        return

    # Step 4: Generate report
    click.echo("Step 4: Generating report...")
    report_result = agent.generate_report(run_result["results"], str(settings.report_output_file))
    if not report_result["success"]:
        click.echo(f"Error in report generation: {report_result['error']}")
        return

    click.echo("Test automation workflow completed successfully!")
    click.echo(f"Tests generated in: {test_result['tests']['output_dir']}")
    click.echo(f"Report generated: {report_result['report_path']}")


@main.command()
@click.option('--project-path', type=click.Path(exists=True), default=str(settings.project_root), help='Path to the project.')
def interactive(project_path: str):
    """
    Start the agent in interactive mode.
    """
    click.echo("Starting interactive session...")
    click.echo("Type 'exit' to quit.")
    agent = TestAutomationAgent(project_path=Path(project_path), settings_obj=settings)

    while True:
        user_input = click.prompt("\nYou>")
        if user_input.lower() in ["exit", "quit"]:
            break

        result_dict = agent.run(user_input)
        if result_dict["success"]:
            click.echo(f"Agent: {result_dict['result']}")
        else:
            click.echo(f"Error: {result_dict['error']}")
