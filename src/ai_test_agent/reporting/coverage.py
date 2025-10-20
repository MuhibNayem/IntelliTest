from datetime import datetime
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Union
from .reporter import TestReporter
from ..config import Settings, settings

class CoverageAnalyzer:
    """Analyze code coverage and generate reports."""
    
    def __init__(self, settings_obj: Settings = settings):
        self.settings = settings_obj
        self.reporter = TestReporter(self.settings)
    
    def analyze_coverage(self, project_path: Union[str, Path]) -> Dict:
        """Analyze code coverage for a project."""
        project_path = Path(project_path)
        
        # Determine project type
        if (project_path / "pyproject.toml").exists() or (project_path / "requirements.txt").exists():
            return self._analyze_python_coverage(project_path)
        elif (project_path / "package.json").exists():
            return self._analyze_js_coverage(project_path)
        elif (project_path / "pom.xml").exists():
            return self._analyze_java_coverage(project_path)
        else:
            return {"error": "Unsupported project type"}
    
    def _analyze_python_coverage(self, project_path: Path) -> Dict:
        # Run coverage.py
        # Add exclude patterns to .coveragerc
        with open(project_path / ".coveragerc", "w") as f:
            f.write("[run]\n")
            f.write(f"omit = {','.join(self.settings.coverage_exclude_patterns)}\n")

        run_result = subprocess.run(
            ["coverage", "run", "-m", "pytest"],
            cwd=project_path,
            check=False,
            capture_output=True,
            text=True
        )

        if run_result.returncode != 0:
            return {"error": "Failed to run pytest with coverage", "details": run_result.stderr}

        json_result = subprocess.run(
            ["coverage", "json"],
            cwd=project_path,
            check=False,
            capture_output=True,
            text=True
        )

        if json_result.returncode != 0:
            return {"error": "Failed to generate coverage.json", "details": json_result.stderr}

        coverage_file = project_path / "coverage.json"
        if coverage_file.exists():
            with open(coverage_file, "r") as f:
                coverage_data = json.load(f)
            # Clean up .coveragerc
            (project_path / ".coveragerc").unlink(missing_ok=True)
            return self._to_unified_format(coverage_data, "python")
        else:
            # Clean up .coveragerc even if coverage.json is not found
            (project_path / ".coveragerc").unlink(missing_ok=True)
            return {"error": "coverage.json not found"}

    def _analyze_js_coverage(self, project_path: Path) -> Dict:
        """Analyze JavaScript code coverage."""
        # Run npm test with coverage
        run_result = subprocess.run(
            ["npm", "test", "--", "--coverage"],
            cwd=project_path,
            check=False,
            capture_output=True,
            text=True
        )

        if run_result.returncode != 0:
            return {"error": "Failed to run npm test with coverage", "details": run_result.stderr}

        # Assuming coverage report is generated at coverage/coverage-summary.json
        coverage_file = project_path / "coverage" / "coverage-summary.json"
        if coverage_file.exists():
            with open(coverage_file, "r") as f:
                coverage_data = json.load(f)
            return self._to_unified_format(coverage_data, "javascript")
        else:
            return {"error": "coverage-summary.json not found. Ensure Jest/Istanbul is configured to output this file."}


    def _analyze_java_coverage(self, project_path: Path) -> Dict:
        """Analyze Java code coverage using JaCoCo and Maven."""
        # Run Maven clean install to execute tests and generate jacoco.exec
        run_result = subprocess.run(
            ["mvn", "clean", "install"],
            cwd=project_path,
            check=False,
            capture_output=True,
            text=True
        )

        if run_result.returncode != 0:
            return {"error": "Failed to run Maven clean install", "details": run_result.stderr}

        # Generate JaCoCo report (XML format)
        report_result = subprocess.run(
            ["mvn", "org.jacoco:jacoco-maven-plugin:report"],
            cwd=project_path,
            check=False,
            capture_output=True,
            text=True
        )

        if report_result.returncode != 0:
            return {"error": "Failed to generate JaCoCo report", "details": report_result.stderr}

        jacoco_xml_file = project_path / "target" / "site" / "jacoco" / "jacoco.xml"
        if jacoco_xml_file.exists():
            coverage_data = self._parse_jacoco_xml(jacoco_xml_file)
            return self._to_unified_format(coverage_data, "java")
        else:
            return {"error": "jacoco.xml not found. Ensure JaCoCo plugin is configured in pom.xml."}

    def _parse_jacoco_xml(self, xml_file: Path) -> Dict:
        """Parse JaCoCo XML report and return a simplified dictionary."""
        import xml.etree.ElementTree as ET

        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Initialize aggregated data
        total_lines_covered = 0
        total_lines_missed = 0
        total_branches_covered = 0
        total_branches_missed = 0
        total_methods_covered = 0
        total_methods_missed = 0

        files_coverage = []

        for package_elem in root.findall(".//package"):
            for class_elem in package_elem.findall(".//class"):
                name = class_elem.get("name") or class_elem.get("sourcefilename") or "Unknown"
                file_name = name.replace(".", "/") if "." in name else name
                if not file_name.endswith(".java"):
                    file_name = file_name + ".java"  

                file_lines_covered = 0
                file_lines_missed = 0
                file_branches_covered = 0
                file_branches_missed = 0
                file_methods_covered = 0
                file_methods_missed = 0

                for counter_elem in class_elem.findall(".//counter"):
                    type = counter_elem.get("type")
                    missed = int(counter_elem.get("missed", 0))
                    covered = int(counter_elem.get("covered", 0))

                    if type == "LINE":
                        file_lines_covered += covered
                        file_lines_missed += missed
                    elif type == "BRANCH":
                        file_branches_covered += covered
                        file_branches_missed += missed
                    elif type == "METHOD":
                        file_methods_covered += covered
                        file_methods_missed += missed
                
                file_total_lines = file_lines_covered + file_lines_missed
                file_total_branches = file_branches_covered + file_branches_missed
                file_total_methods = file_methods_covered + file_methods_missed

                files_coverage.append({
                    "path": file_name,
                    "lines": {"covered": file_lines_covered, "total": file_total_lines, "percent": (file_lines_covered / file_total_lines * 100) if file_total_lines > 0 else 0.0},
                    "branches": {"covered": file_branches_covered, "total": file_total_branches, "percent": (file_branches_covered / file_total_branches * 100) if file_total_branches > 0 else 0.0},
                    "functions": {"covered": file_methods_covered, "total": file_total_methods, "percent": (file_methods_covered / file_total_methods * 100) if file_total_methods > 0 else 0.0},
                    "statements": {"covered": file_lines_covered, "total": file_total_lines, "percent": (file_lines_covered / file_total_lines * 100) if file_total_lines > 0 else 0.0} # JaCoCo lines often map to statements
                })

                total_lines_covered += file_lines_covered
                total_lines_missed += file_lines_missed
                total_branches_covered += file_branches_covered
                total_branches_missed += file_branches_missed
                total_methods_covered += file_methods_covered
                total_methods_missed += file_methods_missed

        total_lines = total_lines_covered + total_lines_missed
        total_branches = total_branches_covered + total_branches_missed
        total_methods = total_methods_covered + total_methods_missed

        return {
            "summary": {
                "lines": {"covered": total_lines_covered, "total": total_lines, "percent": (total_lines_covered / total_lines * 100) if total_lines > 0 else 0.0},
                "branches": {"covered": total_branches_covered, "total": total_branches, "percent": (total_branches_covered / total_branches * 100) if total_branches > 0 else 0.0},
                "functions": {"covered": total_methods_covered, "total": total_methods, "percent": (total_methods_covered / total_methods * 100) if total_methods > 0 else 0.0},
                "statements": {"covered": total_lines_covered, "total": total_lines, "percent": (total_lines_covered / total_lines * 100) if total_lines > 0 else 0.0}
            },
            "files": files_coverage
        }

    def _to_unified_format(self, coverage_data: Dict, language: str) -> Dict:
        """Convert coverage data to a unified format."""
        unified = {
            "language": language,
            "summary": {
                "lines": {"covered": 0, "total": 0, "percent": 0.0},
                "branches": {"covered": 0, "total": 0, "percent": 0.0},
                "functions": {"covered": 0, "total": 0, "percent": 0.0},
                "statements": {"covered": 0, "total": 0, "percent": 0.0}
            },
            "files": []
        }

        if language == "python":
            if "totals" in coverage_data:
                totals = coverage_data["totals"]
                unified["summary"]["lines"]["covered"] = totals.get("covered_lines", 0)
                unified["summary"]["lines"]["total"] = totals.get("num_statements", 0)
                unified["summary"]["lines"]["percent"] = totals.get("percent_covered", 0)
                unified["summary"]["statements"] = unified["summary"]["lines"]

            for file_path, file_data in coverage_data.get("files", {}).items():
                summary = file_data.get("summary", {})
                unified["files"].append({
                    "path": file_path,
                    "lines": {"covered": summary.get("covered_lines", 0), "total": summary.get("num_statements", 0), "percent": summary.get("percent_covered", 0)},
                    "branches": {"covered": 0, "total": 0, "percent": 0.0},
                    "functions": {"covered": 0, "total": 0, "percent": 0.0},
                    "statements": {"covered": summary.get("covered_lines", 0), "total": summary.get("num_statements", 0), "percent": summary.get("percent_covered", 0)}
                })
        elif language == "javascript":
            if "total" in coverage_data:
                total = coverage_data["total"]
                for key in ["lines", "branches", "functions", "statements"]:
                    unified["summary"][key]["covered"] = total.get(key, {}).get("covered", 0)
                    unified["summary"][key]["total"] = total.get(key, {}).get("total", 0)
                    unified["summary"][key]["percent"] = total.get(key, {}).get("pct", 0)

            for file_path, file_data in coverage_data.items():
                if file_path != "total":
                    file_summary = {
                        "path": file_path,
                        "lines": {"covered": file_data.get("l", {}).get("covered", 0), "total": file_data.get("l", {}).get("total", 0), "percent": file_data.get("l", {}).get("pct", 0)},
                        "branches": {"covered": file_data.get("b", {}).get("covered", 0), "total": file_data.get("b", {}).get("total", 0), "percent": file_data.get("b", {}).get("pct", 0)},
                        "functions": {"covered": file_data.get("f", {}).get("covered", 0), "total": file_data.get("f", {}).get("total", 0), "percent": file_data.get("f", {}).get("pct", 0)},
                        "statements": {"covered": file_data.get("s", {}).get("covered", 0), "total": file_data.get("s", {}).get("total", 0), "percent": file_data.get("s", {}).get("pct", 0)}
                    }
                    unified["files"].append(file_summary)
        elif language == "java":
            # The coverage_data from _parse_jacoco_xml is already in the unified format
            return coverage_data

        return unified

    def generate_html_report(self, coverage_data: Dict, output_file: str = "coverage_report.html") -> str:
        """Generate an HTML coverage report."""
        from jinja2 import Environment, BaseLoader
        
        # Create template
        template_str = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Coverage Report</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        margin: 0;
                        padding: 20px;
                        color: #333;
                    }
                    .container {
                        max-width: 1200px;
                        margin: 0 auto;
                    }
                    header {
                        text-align: center;
                        margin-bottom: 30px;
                        padding-bottom: 20px;
                        border-bottom: 1px solid #eee;
                    }
                    h1 {
                        color: #2c3e50;
                        margin-bottom: 10px;
                    }
                    .summary {
                        display: flex;
                        justify-content: space-between;
                        margin-bottom: 30px;
                    }
                    .summary-card {
                        background: #f9f9f9;
                        border-radius: 8px;
                        padding: 20px;
                        flex: 1;
                        margin: 0 10px;
                        text-align: center;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }
                    .summary-card:first-child {
                        margin-left: 0;
                    }
                    .summary-card:last-child {
                        margin-right: 0;
                    }
                    .summary-card h3 {
                        margin-top: 0;
                        color: #2c3e50;
                    }
                    .summary-card .value {
                        font-size: 2em;
                        font-weight: bold;
                        margin: 10px 0;
                    }
                    .high {
                        color: #27ae60;
                    }
                    .medium {
                        color: #f39c12;
                    }
                    .low {
                        color: #e74c3c;
                    }
                    .coverage-table {
                        width: 100%;
                        border-collapse: collapse;
                        margin-bottom: 30px;
                    }
                    .coverage-table th, .coverage-table td {
                        border: 1px solid #ddd;
                        padding: 12px;
                        text-align: left;
                    }
                    .coverage-table th {
                        background-color: #f2f2f2;
                    }
                    .coverage-table tr:nth-child(even) {
                        background-color: #f9f9f9;
                    }
                    .coverage-bar {
                        height: 20px;
                        background-color: #ecf0f1;
                        border-radius: 10px;
                        overflow: hidden;
                    }
                    .coverage-bar .covered {
                        height: 100%;
                        background-color: #27ae60;
                    }
                    footer {
                        text-align: center;
                        margin-top: 30px;
                        padding-top: 20px;
                        border-top: 1px solid #eee;
                        color: #7f8c8d;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <header>
                        <h1>Coverage Report</h1>
                        <p>Generated on {{ timestamp }}</p>
                    </header>
                    
                    <section class="summary">
                        <div class="summary-card">
                            <h3>Lines</h3>
                            <div class="value {{ 'high' if coverage.lines.percent >= 80 else 'medium' if coverage.lines.percent >= 50 else 'low' }}">
                                {{ "%.2f"|format(coverage.lines.percent) }}%
                            </div>
                            <div>{{ coverage.lines.covered }} / {{ coverage.lines.total }}</div>
                        </div>
                        <div class="summary-card">
                            <h3>Branches</h3>
                            <div class="value {{ 'high' if coverage.branches.percent >= 80 else 'medium' if coverage.branches.percent >= 50 else 'low' }}">
                                {{ "%.2f"|format(coverage.branches.percent) }}%
                            </div>
                            <div>{{ coverage.branches.covered }} / {{ coverage.branches.total }}</div>
                        </div>
                        <div class="summary-card">
                            <h3>Functions</h3>
                            <div class="value {{ 'high' if coverage.functions.percent >= 80 else 'medium' if coverage.functions.percent >= 50 else 'low' }}">
                                {{ "%.2f"|format(coverage.functions.percent) }}%
                            </div>
                            <div>{{ coverage.functions.covered }} / {{ coverage.functions.total }}</div>
                        </div>
                        <div class="summary-card">
                            <h3>Statements</h3>
                            <div class="value {{ 'high' if coverage.statements.percent >= 80 else 'medium' if coverage.statements.percent >= 50 else 'low' }}">
                                {{ "%.2f"|format(coverage.statements.percent) }}%
                            </div>
                            <div>{{ coverage.statements.covered }} / {{ coverage.statements.total }}</div>
                        </div>
                    </section>
                    
                    <section>
                        <h2>File Coverage</h2>
                        <table class="coverage-table">
                            <thead>
                                <tr>
                                    <th>File</th>
                                    <th>Lines</th>
                                    <th>Branches</th>
                                    <th>Functions</th>
                                    <th>Statements</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for file in files %}
                                <tr>
                                    <td>{{ file.path }}</td>
                                    <td>
                                        <div class="coverage-bar">
                                            <div class="covered" style="width: {{ file.lines.percent }}%"></div>
                                        </div>
                                        {{ "%.2f"|format(file.lines.percent) }}%
                                    </td>
                                    <td>
                                        <div class="coverage-bar">
                                            <div class="covered" style="width: {{ file.branches.percent }}%"></div>
                                        </div>
                                        {{ "%.2f"|format(file.branches.percent) }}%
                                    </td>
                                    <td>
                                        <div class="coverage-bar">
                                            <div class="covered" style="width: {{ file.functions.percent }}%"></div>
                                        </div>
                                        {{ "%.2f"|format(file.functions.percent) }}%
                                    </td>
                                    <td>
                                        <div class="coverage-bar">
                                            <div class="covered" style="width: {{ file.statements.percent }}%"></div>
                                        </div>
                                        {{ "%.2f"|format(file.statements.percent) }}%
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </section>
                    
                    <footer>
                        <p>Generated by AI Test Agent</p>
                    </footer>
                </div>
            </body>
            </html>
        """
        
        # Process coverage data
        if "error" in coverage_data:
            # Create a simple error report
            template_str = """
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Coverage Report</title>
                </head>
                <body>
                    <h1>Coverage Report</h1>
                    <p>Error: {{ error }}</p>
                </body>
                </html>
            """
            
            env = Environment(loader=BaseLoader())
            template = env.from_string(template_str)
            html_content = template.render(error=coverage_data["error"])
        else:
            # Extract summary and file data
            summary = coverage_data["summary"]
            files = coverage_data["files"]
            
            env = Environment(loader=BaseLoader())
            template = env.from_string(template_str)
            html_content = template.render(
                coverage=summary,
                files=files,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        
        # Write report to file
        report_path = Path(output_file)
        with open(report_path, "w") as f:
            f.write(html_content)
        
        return str(report_path.absolute())
    
    def _extract_coverage_summary(self, coverage_data: Dict) -> Dict:
        """Extract coverage summary from unified coverage data."""
        return coverage_data.get("summary", {})
    
    def _extract_file_coverage(self, coverage_data: Dict) -> List[Dict]:
        """Extract file coverage from unified coverage data."""
        return coverage_data.get("files", [])
        
    def check_coverage_thresholds(self, coverage_data: Dict) -> Dict:
        """Check if coverage thresholds are met."""
        thresholds_met = True
        messages = []

        summary = coverage_data.get("summary", {})

        line_coverage = summary.get("lines", {}).get("percent", 0.0)
        if line_coverage < self.settings.min_line_coverage:
            thresholds_met = False
            messages.append(f"Line coverage ({line_coverage:.2f}%) is below threshold ({self.settings.min_line_coverage}%).")

        branch_coverage = summary.get("branches", {}).get("percent", 0.0)
        if branch_coverage < self.settings.min_branch_coverage:
            thresholds_met = False
            messages.append(f"Branch coverage ({branch_coverage:.2f}%) is below threshold ({self.settings.min_branch_coverage}%).")

        function_coverage = summary.get("functions", {}).get("percent", 0.0)
        if function_coverage < self.settings.min_function_coverage:
            thresholds_met = False
            messages.append(f"Function coverage ({function_coverage:.2f}%) is below threshold ({self.settings.min_function_coverage}%).")

        return {"thresholds_met": thresholds_met, "messages": messages}