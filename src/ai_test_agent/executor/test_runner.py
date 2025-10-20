import asyncio
import json
from pathlib import Path
from typing import Dict, List, Union
from .environment import TestEnvironment
from ..config import Settings, settings
from ..reporting.coverage import CoverageAnalyzer

class TestRunner:
    """Run tests and collect results."""
    
    def __init__(self, project_path: Union[str, None ] = None, settings_obj: Settings = settings):
        self.settings = settings_obj
        self.project_path = Path(project_path) if project_path else self.settings.project_root
        self.test_env = TestEnvironment(self.project_path, self.settings)
        self.coverage_analyzer = CoverageAnalyzer(self.settings)
        self.results = {}
        self.generated_tests_map = {}
        self.test_to_source_map = {}

    def set_generated_tests_map(self, generated_tests_map: Dict[str, str]):
        """Set the map of generated test files to source files."""
        self.generated_tests_map = generated_tests_map
        self.test_to_source_map = {v: k for k, v in generated_tests_map.items()}
    
    async def run_tests(self, test_paths: Union[List[str], None] = None, framework: str = "auto", parallel: bool = False, filter: Union[str, None] = None, run_in_docker: bool = False) -> Dict:
        """Run tests and return results."""
        if test_paths is None:
            # Find test files automatically
            test_paths = await self._find_test_files()
        
        if not test_paths:
            return {"error": "No test files found"}
        
        # Group test paths by framework
        framework_groups = await self._group_by_framework(test_paths, framework)

        if not run_in_docker:
            # Setup test environment
            await self.test_env.setup()

        tasks = []
        for fw, paths in framework_groups.items():
            if fw == "pytest":
                tasks.append(self._run_pytest(paths, filter, run_in_docker))
            elif fw == "jest":
                tasks.append(self._run_jest(paths, filter, run_in_docker))
            elif fw == "junit":
                tasks.append(self._run_junit(paths, filter, run_in_docker))

        if parallel:
            results = await asyncio.gather(*tasks)
        else:
            results = []
            for task in tasks:
                results.append(await task)

        if not run_in_docker:
            # Cleanup test environment
            await self.test_env.cleanup()
        
        # Combine results
        combined_results = {
            "summary": {},
            "tests": []
        }
        for res in results:
            for k, v in res.get("summary", {}).items():
                combined_results["summary"][k] = combined_results["summary"].get(k, 0) + v
            combined_results["tests"].extend(res.get("tests", []))

        # Analyze coverage
        coverage_data = self.coverage_analyzer.analyze_coverage(str(self.project_path))
        combined_results["coverage"] = coverage_data

        # Check coverage thresholds
        threshold_check = self.coverage_analyzer.check_coverage_thresholds(coverage_data)
        combined_results["coverage_threshold_check"] = threshold_check
        if not threshold_check["thresholds_met"]:
            print("Coverage thresholds not met:")
            for msg in threshold_check["messages"]:
                print(f"- {msg}")
            # Optionally, raise an exception or set a failure status

        return combined_results

    async def _group_by_framework(self, test_paths: List[str], framework: str) -> Dict[str, List[str]]:
        """Group test paths by their detected framework."""
        groups = {}
        for path in test_paths:
            fw = framework
            if fw == "auto":
                fw = await self._detect_framework([path])
            
            if fw not in groups:
                groups[fw] = []
            groups[fw].append(path)
        return groups
    
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
        """Detect the test framework based on test files, project configuration, and environment."""
        # Check for executables
        if await self._is_executable("pytest"):
            return "pytest"
        if await self._is_executable("jest"):
            return "jest"
        if await self._is_executable("mvn"):
            return "junit"

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
                    if config == "pyproject.toml":
                        try:
                            import toml
                            with open(self.project_path / config, "r") as f:
                                pyproject = toml.load(f)
                                if "tool" in pyproject and "pytest" in pyproject["tool"]:
                                    return "pytest"
                        except (ImportError, Exception):
                            pass
                    else:
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
                                if "jest" in package_json.get("dependencies", {}) or "jest" in package_json.get("devDependencies", {}):
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

    async def _is_executable(self, name: str) -> bool:
        """Check if a command is executable."""
        process = await asyncio.create_subprocess_exec(
            "which",
            name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        return process.returncode == 0

    async def _run_pytest(self, test_paths: List[str], filter: Union[str, None ] = None, run_in_docker: bool = False) -> Dict:
        """Run pytest tests and stream output in real-time."""
        cmd = ["python", "-m", "pytest", *test_paths, "--json-report", "--json-report-file=test_results.json"]
        if filter:
            cmd.extend(["-k", filter])

        if run_in_docker:
            process = await self.test_env._run_in_docker(cmd)
        else:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        stdout, stderr = b"", b""
        stdout_stream = getattr(process, "stdout", None)
        stderr_stream = getattr(process, "stderr", None)
        while True:
            out_line = b""
            err_line = b""
            if stdout_stream is not None:
                out_line = await stdout_stream.readline()
            if stderr_stream is not None:
                err_line = await stderr_stream.readline()
            if not out_line and not err_line:
                if process.returncode is not None:
                    break
                await asyncio.sleep(0.05)
                continue
            if out_line:
                print(out_line.decode(), end="")
                stdout += out_line
            if err_line:
                print(err_line.decode(), end="")
                stderr += err_line

        await process.wait()

        results = {
            "framework": "pytest",
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8"),
            "stderr": stderr.decode("utf-8"),
            "summary": {},
            "tests": [],
        }

        try:
            with open(self.project_path / "test_results.json", "r") as f:
                json_report = json.load(f)
                results["summary"] = json_report.get("summary", {})

                enriched_tests = []
                for test in json_report.get("tests", []):
                    test_file_path_raw = test.get("nodeid", "").split("::")[0]
                    test_file_path_abs = str(self.project_path / test_file_path_raw)

                    test["test_file_path"] = test_file_path_abs
                    test["source_file_path"] = self.test_to_source_map.get(test_file_path_abs)
                    enriched_tests.append(test)
                results["tests"] = enriched_tests
        except Exception as e:
            print(f"Error reading pytest json report: {e}")
            results["summary"] = self._parse_pytest_output(results["stdout"])

        return results

    async def _run_jest(self, test_paths: List[str], filter: Union[str, None ] = None, run_in_docker: bool = False) -> Dict:
        """Run Jest tests and stream output in real-time."""
        cmd = ["npx", "jest", *test_paths, "--json", "--outputFile=test_results.json"]
        if filter:
            cmd.extend(["-t", filter])

        if run_in_docker:
            process = await self.test_env._run_in_docker(cmd)
        else:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        stdout, stderr = b"", b""
        stdout_stream = getattr(process, "stdout", None)
        stderr_stream = getattr(process, "stderr", None)
        while True:
            out_line = b""
            err_line = b""
            if stdout_stream is not None:
                out_line = await stdout_stream.readline()
            if stderr_stream is not None:
                err_line = await stderr_stream.readline()
            if not out_line and not err_line:
                if process.returncode is not None:
                    break
                await asyncio.sleep(0.05)
                continue
            if out_line:
                print(out_line.decode(), end="")
                stdout += out_line
            if err_line:
                print(err_line.decode(), end="")
                stderr += err_line

        await process.wait()

        results = {
            "framework": "jest",
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8"),
            "stderr": stderr.decode("utf-8"),
            "summary": {},
            "tests": [],
        }

        try:
            with open(self.project_path / "test_results.json", "r") as f:
                json_report = json.load(f)
                results["summary"] = {
                    "total": json_report.get("numTotalTests", 0),
                    "passed": json_report.get("numPassedTests", 0),
                    "failed": json_report.get("numFailedTests", 0),
                    "pending": json_report.get("numPendingTests", 0),
                }
                results["tests"] = []
                for test_file_result in json_report.get("testResults", []):
                    test_file_path_abs = test_file_result.get("testFilePath")
                    if test_file_path_abs:
                        source_file_path = self.test_to_source_map.get(test_file_path_abs)
                        for assertion_result in test_file_result.get("testResults", []):
                            assertion_result["test_file_path"] = test_file_path_abs
                            assertion_result["source_file_path"] = source_file_path
                            results["tests"].append(assertion_result)
        except Exception as e:
            print(f"Error reading jest json report: {e}")
            results["summary"] = self._parse_jest_output(results["stdout"])

        return results

    async def _run_junit(self, test_paths: List[str], filter: Union[str, None ] = None, run_in_docker: bool = False) -> Dict:
        """Run JUnit tests and stream output in real-time."""
        cmd = ["mvn", "test"]
        if filter:
            cmd.append(f"-Dtest={filter}")

        if run_in_docker:
            process = await self.test_env._run_in_docker(cmd)
        else:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        stdout, stderr = b"", b""
        stdout_stream = getattr(process, "stdout", None)
        stderr_stream = getattr(process, "stderr", None)
        while True:
            out_line = b""
            err_line = b""
            if stdout_stream is not None:
                out_line = await stdout_stream.readline()
            if stderr_stream is not None:
                err_line = await stderr_stream.readline()
            if not out_line and not err_line:
                if process.returncode is not None:
                    break
                await asyncio.sleep(0.05)
                continue
            if out_line:
                print(out_line.decode(), end="")
                stdout += out_line
            if err_line:
                print(err_line.decode(), end="")
                stderr += err_line

        await process.wait()

        results = {
            "framework": "junit",
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8"),
            "stderr": stderr.decode("utf-8"),
            "summary": {},
            "tests": [],
        }

        results["summary"] = self._parse_maven_output(results["stdout"])

        surefire_dir = self.project_path / "target" / "surefire-reports"
        if surefire_dir.exists():
            for report_file in surefire_dir.glob("*.xml"):
                try:
                    report_results = self._parse_surefire_report(report_file, test_paths)
                    results["tests"].extend(report_results)
                except Exception as e:
                    print(f"Error parsing surefire report {report_file}: {e}")

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
    
    def _parse_surefire_report(self, report_file: Path, test_paths: List[str]) -> List[Dict]:
        """Parse a JUnit surefire XML report."""
        import xml.etree.ElementTree as ET
        
        tree = ET.parse(report_file)
        root = tree.getroot()
        
        tests = []
        test_file_path_abs = str(report_file.absolute())
        source_file_path = self.test_to_source_map.get(test_file_path_abs)

        for testcase in root.findall("testcase"):
            test = {
                "name": testcase.get("name"),
                "classname": testcase.get("classname"),
                "time": float(testcase.get("time", 0)),
                "status": "passed",
                "test_file_path": test_file_path_abs,
                "source_file_path": source_file_path
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
