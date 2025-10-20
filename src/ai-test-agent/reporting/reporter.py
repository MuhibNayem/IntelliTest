import json
from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime

class TestReporter:
    """Generate test reports in various formats."""
    
    def __init__(self):
        self.templates_dir = Path(__file__).parent.parent / "templates"
        self.templates_dir.mkdir(exist_ok=True)
        self._setup_templates()
    
    def _setup_templates(self):
        """Setup report templates."""
        # HTML report template
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report</title>
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
        .passed {
            color: #27ae60;
        }
        .failed {
            color: #e74c3c;
        }
        .skipped {
            color: #f39c12;
        }
        .errors {
            color: #9b59b6;
        }
        .progress-bar {
            height: 20px;
            background-color: #ecf0f1;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        .progress-bar .passed {
            height: 100%;
            background-color: #27ae60;
            float: left;
        }
        .progress-bar .failed {
            height: 100%;
            background-color: #e74c3c;
            float: left;
        }
        .progress-bar .skipped {
            height: 100%;
            background-color: #f39c12;
            float: left;
        }
        .progress-bar .errors {
            height: 100%;
            background-color: #9b59b6;
            float: left;
        }
        .test-suites {
            margin-top: 30px;
        }
        .test-suite {
            margin-bottom: 20px;
            border: 1px solid #eee;
            border-radius: 8px;
            overflow: hidden;
        }
        .test-suite-header {
            background: #f1f1f1;
            padding: 15px;
            font-weight: bold;
        }
        .test-suite-content {
            padding: 15px;
        }
        .test-case {
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
        .test-case:last-child {
            border-bottom: none;
        }
        .test-case.passed {
            background-color: rgba(39, 174, 96, 0.1);
        }
        .test-case.failed {
            background-color: rgba(231, 76, 60, 0.1);
        }
        .test-case.skipped {
            background-color: rgba(243, 156, 18, 0.1);
        }
        .test-case.errors {
            background-color: rgba(155, 89, 182, 0.1);
        }
        .test-case-name {
            font-weight: bold;
        }
        .test-case-status {
            float: right;
            font-weight: bold;
        }
        .test-case-details {
            margin-top: 10px;
            font-family: monospace;
            background: #f9f9f9;
            padding: 10px;
            border-radius: 4px;
            white-space: pre-wrap;
            overflow-x: auto;
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
            <h1>Test Report</h1>
            <p>Generated on {{ timestamp }}</p>
        </header>
        
        <section class="summary">
            <div class="summary-card">
                <h3>Total Tests</h3>
                <div class="value">{{ summary.total_tests }}</div>
            </div>
            <div class="summary-card">
                <h3>Passed</h3>
                <div class="value passed">{{ summary.passed }}</div>
            </div>
            <div class="summary-card">
                <h3>Failed</h3>
                <div class="value failed">{{ summary.failed }}</div>
            </div>
            <div class="summary-card">
                <h3>Skipped</h3>
                <div class="value skipped">{{ summary.skipped }}</div>
            </div>
            <div class="summary-card">
                <h3>Errors</h3>
                <div class="value errors">{{ summary.errors }}</div>
            </div>
            <div class="summary-card">
                <h3>Pass Rate</h3>
                <div class="value">{{ "%.2f"|format(summary.pass_rate) }}%</div>
            </div>
        </section>
        
        <section class="progress-bar">
            {% if summary.total_tests > 0 %}
            <div class="passed" style="width: {{ (summary.passed / summary.total_tests) * 100 }}%"></div>
            <div class="failed" style="width: {{ (summary.failed / summary.total_tests) * 100 }}%"></div>
            <div class="skipped" style="width: {{ (summary.skipped / summary.total_tests) * 100 }}%"></div>
            <div class="errors" style="width: {{ (summary.errors / summary.total_tests) * 100 }}%"></div>
            {% endif %}
        </section>
        
        <section class="test-suites">
            <h2>Test Suites</h2>
            {% for suite in details %}
            <div class="test-suite">
                <div class="test-suite-header">
                    {{ suite.framework }} Test Suite
                </div>
                <div class="test-suite-content">
                    <div class="summary">
                        <div class="summary-card">
                            <h3>Total</h3>
                            <div class="value">{{ suite.summary.total }}</div>
                        </div>
                        <div class="summary-card">
                            <h3>Passed</h3>
                            <div class="value passed">{{ suite.summary.passed }}</div>
                        </div>
                        <div class="summary-card">
                            <h3>Failed</h3>
                            <div class="value failed">{{ suite.summary.failed }}</div>
                        </div>
                        <div class="summary-card">
                            <h3>Skipped</h3>
                            <div class="value skipped">{{ suite.summary.skipped }}</div>
                        </div>
                        <div class="summary-card">
                            <h3>Errors</h3>
                            <div class="value errors">{{ suite.summary.errors }}</div>
                        </div>
                    </div>
                    
                    {% for test in suite.tests %}
                    <div class="test-case {{ test.status }}">
                        <div class="test-case-name">{{ test.name }}</div>
                        <div class="test-case-status">{{ test.status|title }}</div>
                        {% if test.message %}
                        <div class="test-case-details">{{ test.message }}</div>
                        {% endif %}
                        {% if test.traceback %}
                        <div class="test-case-details">{{ test.traceback }}</div>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </section>
        
        <footer>
            <p>Generated by AI Test Agent</p>
        </footer>
    </div>
</body>
</html>
        """
        
        # Write template to file
        with open(self.templates_dir / "html_report.j2", "w") as f:
            f.write(html_template)
    
    def generate_html_report(self, test_results: Dict, output_file: str = "test_report.html") -> str:
        """Generate an HTML test report."""
        from jinja2 import Environment, FileSystemLoader
        
        # Setup template environment
        env = Environment(loader=FileSystemLoader(self.templates_dir))
        template = env.get_template("html_report.j2")
        
        # Render template
        html_content = template.render(
            summary=test_results.get("summary", {}),
            details=test_results.get("details", []),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # Write report to file
        report_path = Path(output_file)
        with open(report_path, "w") as f:
            f.write(html_content)
        
        return str(report_path.absolute())
    
    def generate_json_report(self, test_results: Dict, output_file: str = "test_report.json") -> str:
        """Generate a JSON test report."""
        report_path = Path(output_file)
        
        with open(report_path, "w") as f:
            json.dump(test_results, f, indent=2)
        
        return str(report_path.absolute())
    
    def generate_xml_report(self, test_results: Dict, output_file: str = "test_report.xml") -> str:
        """Generate an XML test report (JUnit format)."""
        from xml.etree.ElementTree import Element, SubElement, tostring
        from xml.dom import minidom
        
        # Create root element
        testsuites = Element("testsuites")
        testsuites.set("tests", str(test_results.get("summary", {}).get("total_tests", 0)))
        testsuites.set("failures", str(test_results.get("summary", {}).get("failed", 0)))
        testsuites.set("errors", str(test_results.get("summary", {}).get("errors", 0)))
        testsuites.set("time", str(test_results.get("summary", {}).get("duration", 0)))
        
        # Add test suites
        for suite in test_results.get("details", []):
            testsuite = SubElement(testsuites, "testsuite")
            testsuite.set("name", suite.get("framework", "unknown"))
            testsuite.set("tests", str(suite.get("summary", {}).get("total", 0)))
            testsuite.set("failures", str(suite.get("summary", {}).get("failed", 0)))
            testsuite.set("errors", str(suite.get("summary", {}).get("errors", 0)))
            testsuite.set("time", str(suite.get("summary", {}).get("duration", 0)))
            
            # Add test cases
            for test in suite.get("tests", []):
                testcase = SubElement(testsuite, "testcase")
                testcase.set("name", test.get("name", "unknown"))
                testcase.set("classname", test.get("classname", ""))
                testcase.set("time", str(test.get("time", 0)))
                
                # Add failure, error, or skipped elements
                if test.get("status") == "failed":
                    failure = SubElement(testcase, "failure")
                    failure.set("message", test.get("message", ""))
                    failure.text = test.get("traceback", "")
                elif test.get("status") == "error":
                    error = SubElement(testcase, "error")
                    error.set("message", test.get("message", ""))
                    error.text = test.get("traceback", "")
                elif test.get("status") == "skipped":
                    skipped = SubElement(testcase, "skipped")
                    skipped.set("message", test.get("message", ""))
        
        # Pretty print XML
        rough_string = tostring(testsuites, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")
        
        # Write report to file
        report_path = Path(output_file)
        with open(report_path, "w") as f:
            f.write(pretty_xml)
        
        return str(report_path.absolute())