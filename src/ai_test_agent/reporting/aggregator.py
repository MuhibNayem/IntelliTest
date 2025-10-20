import json
from pathlib import Path
from typing import Dict, List, Union
from datetime import datetime
from .reporter import TestReporter
from .coverage import CoverageAnalyzer
from ..config import Settings, settings

class ResultsAggregator:
    """Aggregate test results and generate reports."""
    
    def __init__(self, settings_obj: Settings = settings):
        self.settings = settings_obj
        self.reporter = TestReporter(self.settings)
        self.coverage_analyzer = CoverageAnalyzer(self.settings)
        self.history_file = self.settings.project_root / "test_history.json"
    
    def aggregate_results(self, test_results: List[Dict]) -> Dict:
        """Aggregate multiple test results into a single summary."""
        if not test_results:
            return {"error": "No test results provided"}
        
        # Initialize summary
        summary = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 0,
            "test_suites": len(test_results),
            "timestamp": datetime.now().isoformat()
        }
        
        # Aggregate results from each test suite
        detailed_results = []
        for result in test_results:
            framework = result.get("framework", "unknown")
            suite_summary = result.get("summary", {})
            tests = result.get("tests", [])
            
            # Update summary
            summary["total_tests"] += suite_summary.get("total", 0)
            summary["passed"] += suite_summary.get("passed", 0)
            summary["failed"] += suite_summary.get("failed", 0)
            summary["skipped"] += suite_summary.get("skipped", 0)
            summary["errors"] += suite_summary.get("errors", 0)
            summary["duration"] += suite_summary.get("duration", 0)
            
            # Add detailed results
            detailed_results.append({
                "framework": framework,
                "summary": suite_summary,
                "tests": tests
            })
        
        # Calculate pass rate
        if summary["total_tests"] > 0:
            summary["pass_rate"] = (summary["passed"] / summary["total_tests"]) * 100
        else:
            summary["pass_rate"] = 0
        
        aggregated_results = {
            "summary": summary,
            "details": detailed_results
        }

        self._store_historical_data(aggregated_results)

        return aggregated_results

    def _store_historical_data(self, results: Dict):
        """Store aggregated test results for trend analysis."""
        history = []
        if self.history_file.exists():
            with open(self.history_file, "r") as f:
                try:
                    history = json.load(f)
                except json.JSONDecodeError:
                    pass
        
        history.append(results)

        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=2)
    
    def generate_report(self, test_results: Union[Dict, List[Dict]], output_file: str = str(settings.report_output_file)) -> str:
        """Generate a test report."""
        # Normalize single-result dict to a list and ensure correct typing for aggregate_results
        if isinstance(test_results, dict) and "summary" in test_results:
            test_results_list: List[Dict] = [test_results]
        elif isinstance(test_results, list):
            test_results_list = test_results
        else:
            # Fallback: wrap any other value into a list
            test_results_list = [test_results]  # type: ignore[arg-type]
        
        # Aggregate results
        aggregated = self.aggregate_results(test_results_list)
        
        # Determine output path relative to the configured project root
        output_path = Path(output_file)
        if not output_path.is_absolute():
            output_path = (self.settings.project_root / output_path).resolve()

        template_path = ""
        if self.reporter.templates_dir.exists():
            default_template = self.reporter.templates_dir / "html_report.j2"
            template_path = str(default_template) if default_template.exists() else ""

        report_path = self.reporter.generate_html_report(
            aggregated,
            str(output_path),
            template_path
        )
        
        return report_path
    
    def generate_coverage_report(self, project_path: str, output_file: str = str(settings.coverage_output_file)) -> str:
        """Generate a coverage report."""
        coverage_data = self.coverage_analyzer.analyze_coverage(project_path)
        output_path = Path(output_file)
        if not output_path.is_absolute():
            output_path = (self.settings.project_root / output_path).resolve()

        report_path = self.coverage_analyzer.generate_html_report(coverage_data, str(output_path))
        return report_path
