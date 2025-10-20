import json
from pathlib import Path
from typing import Dict
from datetime import datetime
from ..config import Settings, settings

class TestReporter:
    """Generate test reports in various formats."""
    
    def __init__(self, settings_obj: Settings = settings):
        self.settings = settings_obj
        self.templates_dir = Path(__file__).parent.parent / "generator" / "templates"
    
    def generate_html_report(self, test_results: Dict, output_file: str , template_path: str ) -> str:
        """Generate an HTML test report."""
        if output_file is None:
            output_file = self.settings.report_output_file
        from jinja2 import Environment, FileSystemLoader
        
        # Setup template environment
        if template_path:
            template_dir = Path(template_path).parent
            template_name = Path(template_path).name
            env = Environment(loader=FileSystemLoader(template_dir))
            template = env.get_template(template_name)
        else:
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
    
    def generate_json_report(self, test_results: Dict, output_file: str) -> str:
        """Generate a JSON test report."""
        if output_file is None:
            output_file = self.settings.results_output_file
        report_path = Path(output_file)
        
        with open(report_path, "w") as f:
            json.dump(test_results, f, indent=2)
        
        return str(report_path.absolute())
    
    def generate_xml_report(self, test_results: Dict, output_file: str) -> str:
        """Generate an XML test report (JUnit format)."""
        if output_file is None:
            output_file = self.settings.xml_report_output_file
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