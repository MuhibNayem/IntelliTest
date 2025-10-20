import asyncio
import json
from pathlib import Path
from typing import Dict, List
from .environment import TestEnvironment
from ..config import Settings, settings

class TestRunner:
    """Run tests and collect results."""
    
    def __init__(self, project_path: str = None, settings_obj: Settings = settings):
        self.settings = settings_obj
        self.project_path = Path(project_path) if project_path else self.settings.project_root
        self.test_env = TestEnvironment(self.project_path, self.settings)
        self.results = {}
    
    async def run_tests(self, test_paths: List[str] = None, framework: str = "auto") -> Dict:
        """Run tests and return results."""
        if test_paths is None:
            # Find test files automatically
            test_paths = await self._find_test_files()
        
        if not test_paths:
            return {"error": "No test files found"}
        
        # Determine test framework
        if framework == "auto":
            framework = await self._detect_framework(test_paths)
        
        # Setup test environment
        await self.test_env.setup()
        
        # Run tests based on framework
        if framework == "pytest":
            results = await self._run_pytest(test_paths)
        elif framework == "jest":
            results = await self._run_jest(test_paths)
        elif framework == "junit":
            results = await self._run_junit(test_paths)
        else:
            results = {"error": f"Unsupported test framework: {framework}"}
        
        # Cleanup test environment
        await self.test_env.cleanup()
        
        return results
    
    async def _find_test_files(self) -> List[str]:
        """Find test files in the project."""
        test_patterns = [
            "**/*test*.py",
            "**/test_*.py",
            "**/*test*.js",
            "**/*.test.js",
            "**/*test*.java",
            "**/*Test.java"
        ]
        
        test_files = []
        for pattern in test_patterns:
            for file_path in self.project_path.glob(pattern):
                if file_path.is_file():
                    test_files.append(str(file_path))
        
        return test_files
    
    async def _detect_framework(self, test_paths: List[str]) -> str:
        """Detect the test framework based on test files and project configuration."""
        # Check for pytest
        if any(path.endswith(".py") for path in test_paths):
            # Check for pytest configuration
            pytest_configs = [
                "pytest.ini",
                "pyproject.toml",
                "setup.cfg",
                "tox.ini"
            ]
            
            for config in pytest_configs:
                if (self.project_path / config).exists():
                    return "pytest"
            
            # Default to pytest for Python projects
            return "pytest"
        
        # Check for Jest
        if any(path.endswith((".js", ".jsx", ".ts", ".tsx")) for path in test_paths):
            # Check for Jest configuration
            jest_configs = [
                "jest.config.js",
                "jest.config.json",
                "jest.config.ts",
                "package.json"
            ]
            
            for config in jest_configs:
                if (self.project_path / config).exists():
                    if config == "package.json":
                        # Check if jest is in package.json
                        try:
                            with open(self.project_path / config, "r") as f:
                                package_json = json.load(f)
                                if "jest" in package_json or "devDependencies" in package_json and "jest" in package_json["devDependencies"]:
                                    return "jest"
                        except:
                            pass
                    else:
                        return "jest"
            
            # Default to Jest for JavaScript/TypeScript projects
            return "jest"
        
        # Check for JUnit
        if any(path.endswith(".java") for path in test_paths):
            # Check for JUnit dependencies
            pom_xml = self.project_path / "pom.xml"
            build_gradle = self.project_path / "build.gradle"
            
            if pom_xml.exists():
                try:
                    with open(pom_xml, "r") as f:
                        content = f.read()
                        if "junit" in content.lower():
                            return "junit"
                except:
                    pass
            
            if build_gradle.exists():
                try:
                    with open(build_gradle, "r") as f:
                        content = f.read()
                        if "junit" in content.lower():
                            return "junit"
                except:
                    pass
            
            # Default to JUnit for Java projects
            return "junit"
        
        return "unknown"
    
    async def _run_pytest(self, test_paths: List[str]) -> Dict:
        """Run pytest tests."""
        # Prepare pytest command
        cmd = ["python", "-m", "pytest"]
        
        # Add test paths
        cmd.extend(test_paths)
        
        # Add options for JSON output
        cmd.extend(["--json-report", "--json-report-file=test_results.json"])
        
        # Run pytest
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Parse results
        results = {
            "framework": "pytest",
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8"),
            "stderr": stderr.decode("utf-8"),
            "summary": {},
            "tests": []
        }
        
        # Try to parse JSON report
        try:
            with open(self.project_path / "test_results.json", "r") as f:
                json_report = json.load(f)
                results["summary"] = json_report.get("summary", {})
                results["tests"] = json_report.get("tests", [])
        except:
            # Fallback to parsing stdout
            results["summary"] = self._parse_pytest_output(results["stdout"])
        
        return results
    
    async def _run_jest(self, test_paths: List[str]) -> Dict:
        """Run Jest tests."""
        # Prepare Jest command
        cmd = ["npx", "jest"]
        
        # Add test paths
        cmd.extend(test_paths)
        
        # Add options for JSON output
        cmd.extend(["--json", "--outputFile=test_results.json"])
        
        # Run Jest
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Parse results
        results = {
            "framework": "jest",
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8"),
            "stderr": stderr.decode("utf-8"),
            "summary": {},
            "tests": []
        }
        
        # Try to parse JSON report
        try:
            with open(self.project_path / "test_results.json", "r") as f:
                json_report = json.load(f)
                results["summary"] = {
                    "total": json_report.get("numTotalTests", 0),
                    "passed": json_report.get("numPassedTests", 0),
                    "failed": json_report.get("numFailedTests", 0),
                    "pending": json_report.get("numPendingTests", 0)
                }
                results["tests"] = json_report.get("testResults", [])
        except:
            # Fallback to parsing stdout
            results["summary"] = self._parse_jest_output(results["stdout"])
        
        return results
    
    async def _run_junit(self, test_paths: List[str]) -> Dict:
        """Run JUnit tests."""
        # Prepare Maven command
        cmd = ["mvn", "test"]
        
        # Run Maven
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Parse results
        results = {
            "framework": "junit",
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8"),
            "stderr": stderr.decode("utf-8"),
            "summary": {},
            "tests": []
        }
        
        # Try to parse test results from Maven output
        results["summary"] = self._parse_maven_output(results["stdout"])
        
        # Try to parse surefire reports
        surefire_dir = self.project_path / "target" / "surefire-reports"
        if surefire_dir.exists():
            for report_file in surefire_dir.glob("*.xml"):
                try:
                    report_results = self._parse_surefire_report(report_file)
                    results["tests"].extend(report_results)
                except:
                    pass
        
        return results
    
    def _parse_pytest_output(self, output: str) -> Dict:
        """Parse pytest output to extract summary."""
        summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0
        }
        
        lines = output.split("\n")
        for line in lines:
            if "=" in line and "passed" in line:
                # Example: "5 passed, 2 failed, 1 skipped in 0.12s"
                parts = line.split("=")[1].strip().split(" in ")[0].split(", ")
                for part in parts:
                    if "passed" in part:
                        summary["passed"] = int(part.split(" ")[0])
                    elif "failed" in part:
                        summary["failed"] = int(part.split(" ")[0])
                    elif "skipped" in part:
                        summary["skipped"] = int(part.split(" ")[0])
                    elif "error" in part:
                        summary["errors"] = int(part.split(" ")[0])
        
        summary["total"] = summary["passed"] + summary["failed"] + summary["skipped"] + summary["errors"]
        return summary
    
    def _parse_jest_output(self, output: str) -> Dict:
        """Parse Jest output to extract summary."""
        summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pending": 0
        }
        
        lines = output.split("\n")
        for line in lines:
            if "Tests:" in line:
                # Example: "Tests:       1 passed, 2 failed"
                parts = line.split(":")[1].strip().split(", ")
                for part in parts:
                    if "passed" in part:
                        summary["passed"] = int(part.split(" ")[0])
                    elif "failed" in part:
                        summary["failed"] = int(part.split(" ")[0])
                    elif "pending" in part:
                        summary["pending"] = int(part.split(" ")[0])
        
        summary["total"] = summary["passed"] + summary["failed"] + summary["pending"]
        return summary
    
    def _parse_maven_output(self, output: str) -> Dict:
        """Parse Maven output to extract summary."""
        summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0
        }
        
        lines = output.split("\n")
        for line in lines:
            if "Tests run:" in line:
                # Example: "Tests run: 5, Failures: 1, Errors: 0, Skipped: 0"
                parts = line.split(", ")
                for part in parts:
                    if "Tests run:" in part:
                        summary["total"] = int(part.split(":")[1].strip())
                    elif "Failures:" in part:
                        summary["failed"] = int(part.split(":")[1].strip())
                    elif "Errors:" in part:
                        summary["errors"] = int(part.split(":")[1].strip())
                    elif "Skipped:" in part:
                        summary["skipped"] = int(part.split(":")[1].strip())
        
        summary["passed"] = summary["total"] - summary["failed"] - summary["errors"] - summary["skipped"]
        return summary
    
    def _parse_surefire_report(self, report_file: Path) -> List[Dict]:
        """Parse a JUnit surefire XML report."""
        import xml.etree.ElementTree as ET
        
        tree = ET.parse(report_file)
        root = tree.getroot()
        
        tests = []
        for testcase in root.findall("testcase"):
            test = {
                "name": testcase.get("name"),
                "classname": testcase.get("classname"),
                "time": float(testcase.get("time", 0)),
                "status": "passed"
            }
            
            failure = testcase.find("failure")
            if failure is not None:
                test["status"] = "failed"
                test["message"] = failure.get("message")
                test["traceback"] = failure.text
            
            error = testcase.find("error")
            if error is not None:
                test["status"] = "error"
                test["message"] = error.get("message")
                test["traceback"] = error.text
            
            skipped = testcase.find("skipped")
            if skipped is not None:
                test["status"] = "skipped"
                test["message"] = skipped.get("message")
            
            tests.append(test)
        
        return tests