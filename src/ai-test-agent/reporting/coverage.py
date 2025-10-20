import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union
from .reporter import TestReporter

class CoverageAnalyzer:
    """Analyze code coverage and generate reports."""
    
    def __init__(self):
        self.reporter = TestReporter()
    
    def analyze_coverage(self, project_path: str) -> Dict:
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
        """Analyze Python code coverage."""
        # Run coverage.py
        try:
            # Install coverage if not already installed
            subprocess.run(
                ["pip", "install", "coverage"],
                cwd=project_path,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Run coverage
            subprocess.run(
                ["coverage", "run", "-m", "pytest"],
                cwd=project_path,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Generate coverage report
            result = subprocess.run(
                ["coverage", "json", "-o", "coverage.json"],
                cwd=project_path,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            if result.returncode == 0:
                with open(project_path / "coverage.json", "r") as f:
                    coverage_data = json.load(f)
                return coverage_data
            else:
                return {"error": "Failed to generate coverage report"}
        except Exception as e:
            return {"error": str(e)}
    
    def _analyze_js_coverage(self, project_path: Path) -> Dict:
        """Analyze JavaScript code coverage."""
        try:
            # Check if jest is configured for coverage
            package_json_path = project_path / "package.json"
            if package_json_path.exists():
                with open(package_json_path, "r+") as f:
                    package_json = json.load(f)
                    jest_config = package_json.get("jest", {})
                    if "collectCoverage" not in jest_config:
                        # Update package.json to enable coverage
                        jest_config["collectCoverage"] = True
                        jest_config["coverageDirectory"] = "coverage"
                        jest_config["coverageReporters"] = ["json", "text", "lcov"]
                        package_json["jest"] = jest_config
                        f.seek(0)
                        json.dump(package_json, f, indent=2)
                        f.truncate()
            
            # Run tests with coverage
            result = subprocess.run(
                ["npm", "test", "--", "--coverage"],
                cwd=project_path,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Read coverage report
            coverage_file = project_path / "coverage" / "coverage-final.json"
            if coverage_file.exists():
                with open(coverage_file, "r") as f:
                    coverage_data = json.load(f)
                return coverage_data
            else:
                return {"error": "Coverage report not found"}
        except Exception as e:
            return {"error": str(e)}
    
    def _analyze_java_coverage(self, project_path: Path) -> Dict:
        """Analyze Java code coverage."""
        try:
            # Check if JaCoCo is configured
            pom_xml_path = project_path / "pom.xml"
            if pom_xml_path.exists():
                import xml.etree.ElementTree as ET
                tree = ET.parse(pom_xml_path)
                root = tree.getroot()
                # Check if jacoco plugin is already present
                if not root.find(".//artifactId[.='jacoco-maven-plugin']"):
                    # Find the plugins element
                    plugins = root.find(".//plugins")
                    if plugins is None:
                        build = root.find(".//build")
                        if build is None:
                            build = ET.Element("build")
                            root.append(build)
                        plugins = ET.SubElement(build, "plugins")

                    # Add JaCoCo plugin
                    jacoco_plugin = ET.fromstring("""
            <plugin>
                <groupId>org.jacoco</groupId>
                <artifactId>jacoco-maven-plugin</artifactId>
                <version>0.8.7</version>
                <executions>
                    <execution>
                        <goals>
                            <goal>prepare-agent</goal>
                        </goals>
                    </execution>
                    <execution>
                        <id>report</id>
                        <phase>test</phase>
                        <goals>
                            <goal>report</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
                    """)
                    plugins.append(jacoco_plugin)
                    tree.write(pom_xml_path)
            
            # Run tests with coverage
            subprocess.run(
                ["mvn", "test"],
                cwd=project_path,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Read coverage report
            coverage_file = project_path / "target" / "site" / "jacoco" / "jacoco.json"
            if coverage_file.exists():
                with open(coverage_file, "r") as f:
                    coverage_data = json.load(f)
                return coverage_data
            else:
                return {"error": "Coverage report not found"}
        except Exception as e:
            return {"error": str(e)}
    
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
            summary = self._extract_coverage_summary(coverage_data)
            files = self._extract_file_coverage(coverage_data)
            
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
        """Extract coverage summary from coverage data."""
        # This is a simplified implementation
        # In a real implementation, this would handle different coverage formats
        
        if "totals" in coverage_data:
            # Coverage.py format
            totals = coverage_data["totals"]
            return {
                "lines": {
                    "covered": totals.get("covered_lines", 0),
                    "total": totals.get("num_statements", 0),
                    "percent": totals.get("percent_covered", 0) * 100
                },
                "branches": {
                    "covered": totals.get("covered_branches", 0),
                    "total": totals.get("num_branches", 0),
                    "percent": 0  # Not available in coverage.py
                },
                "functions": {
                    "covered": 0,  # Not available in coverage.py
                    "total": 0,
                    "percent": 0
                },
                "statements": {
                    "covered": totals.get("covered_lines", 0),
                    "total": totals.get("num_statements", 0),
                    "percent": totals.get("percent_covered", 0) * 100
                }
            }
        elif "total" in coverage_data:
            # Jest format
            total = coverage_data["total"]
            return {
                "lines": {
                    "covered": total.get("lines", {}).get("covered", 0),
                    "total": total.get("lines", {}).get("total", 0),
                    "percent": total.get("lines", {}).get("pct", 0)
                },
                "branches": {
                    "covered": total.get("branches", {}).get("covered", 0),
                    "total": total.get("branches", {}).get("total", 0),
                    "percent": total.get("branches", {}).get("pct", 0)
                },
                "functions": {
                    "covered": total.get("functions", {}).get("covered", 0),
                    "total": total.get("functions", {}).get("total", 0),
                    "percent": total.get("functions", {}).get("pct", 0)
                },
                "statements": {
                    "covered": total.get("statements", {}).get("covered", 0),
                    "total": total.get("statements", {}).get("total", 0),
                    "percent": total.get("statements", {}).get("pct", 0)
                }
            }
        else:
            # Default/unknown format
            return {
                "lines": {"covered": 0, "total": 0, "percent": 0},
                "branches": {"covered": 0, "total": 0, "percent": 0},
                "functions": {"covered": 0, "total": 0, "percent": 0},
                "statements": {"covered": 0, "total": 0, "percent": 0}
            }
    
    def _extract_file_coverage(self, coverage_data: Dict) -> List[Dict]:
        """Extract file coverage from coverage data."""
        files = []
        
        if "files" in coverage_data:
            # Coverage.py or Jest format
            for file_path, file_data in coverage_data["files"].items():
                if "summary" in file_data:
                    # Coverage.py format
                    summary = file_data["summary"]
                    files.append({
                        "path": file_path,
                        "lines": {
                            "covered": summary.get("covered_lines", 0),
                            "total": summary.get("num_statements", 0),
                            "percent": summary.get("percent_covered", 0) * 100
                        },
                        "branches": {
                            "covered": 0,  # Not available in coverage.py
                            "total": 0,
                            "percent": 0
                        },
                        "functions": {
                            "covered": 0,  # Not available in coverage.py
                            "total": 0,
                            "percent": 0
                        },
                        "statements": {
                            "covered": summary.get("covered_lines", 0),
                            "total": summary.get("num_statements", 0),
                            "percent": summary.get("percent_covered", 0) * 100
                        }
                    })
                else:
                    # Jest format
                    files.append({
                        "path": file_path,
                        "lines": {
                            "covered": file_data.get("l", {}).get("covered", 0),
                            "total": file_data.get("l", {}).get("total", 0),
                            "percent": file_data.get("l", {}).get("pct", 0)
                        },
                        "branches": {
                            "covered": file_data.get("b", {}).get("covered", 0),
                            "total": file_data.get("b", {}).get("total", 0),
                            "percent": file_data.get("b", {}).get("pct", 0)
                        },
                        "functions": {
                            "covered": file_data.get("f", {}).get("covered", 0),
                            "total": file_data.get("f", {}).get("total", 0),
                            "percent": file_data.get("f", {}).get("pct", 0)
                        },
                        "statements": {
                            "covered": file_data.get("s", {}).get("covered", 0),
                            "total": file_data.get("s", {}).get("total", 0),
                            "percent": file_data.get("s", {}).get("pct", 0)
                        }
                    })
        
        return files