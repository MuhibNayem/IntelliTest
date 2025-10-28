import asyncio
import json
from threading import Thread
from typing import Dict, Optional, Iterable
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ..explorer.file_tools import FileTools
from ..explorer.analyzer import ProjectAnalyzer
from ..generator.test_generator import TestGenerator
from ..executor.test_runner import TestRunner
from ..reporting.aggregator import ResultsAggregator


def _run_coroutine_sync(coro):
    """Execute an asyncio coroutine from sync context, even if a loop is running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result_container = {}
    error_container = {}

    def _runner():
        try:
            result_container["value"] = asyncio.run(coro)
        except Exception as exc:  # pragma: no cover - propagate outside loop context
            error_container["error"] = exc

    thread = Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_container:
        raise error_container["error"]
    return result_container.get("value")


_DANGEROUS_TOKENS = {
    "rm",
    "del",
    "shutdown",
    "reboot",
    "mkfs",
    "dd",
    ">",
    "|",
    "&&",
    ";",
}


def _validate_shell_command(command: str) -> None:
    """Best-effort guard against destructive shell commands."""
    lowered = command.lower()
    if any(token in lowered for token in _DANGEROUS_TOKENS):
        raise ValueError(
            "Command rejected for safety. Use manual shell access for potentially destructive operations."
        )


def _coerce_params(
    args: Iterable,
    kwargs: Dict,
    *,
    defaults: Optional[Dict] = None,
    positional_key: Optional[str] = None,
) -> Dict:
    params: Dict = dict(defaults or {})
    params.update(kwargs or {})
    if not kwargs and args:
        # Only consider the first positional argument for these simple tools.
        first = args[0]
        if isinstance(first, dict):
            params.update(first)
        elif isinstance(first, str):
            try:
                parsed = json.loads(first)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                params.update(parsed)
            elif positional_key:
                params[positional_key] = first
        elif positional_key:
            params[positional_key] = first
    return params


def _ensure_required(params: Dict, required: Iterable[str]) -> None:
    missing = [key for key in required if key not in params or params[key] is None]
    if missing:
        raise ValueError(f"Missing required argument(s): {', '.join(missing)}")


class ReadFileTool(BaseTool):
    """Tool for reading files."""
    name: str = "read_file"
    description: str = "Reads the content of a specified file. Input is 'file_path' (string), the absolute or relative path to the file. Returns the file content as a string."

    class InputSchema(BaseModel):
        file_path: str = Field(..., description="The path to the file to read")

    args_schema = InputSchema
    file_tools: FileTools

    def __init__(self, file_tools: FileTools, **kwargs):
        super().__init__(file_tools=file_tools, **kwargs)
    
    def _run(self, *args, **kwargs) -> str:
        """Read the contents of a file."""
        params = _coerce_params(args, kwargs, positional_key="file_path")
        _ensure_required(params, ["file_path"])
        return _run_coroutine_sync(self.file_tools.read_file(params["file_path"]))
    
    async def _arun(self, *args, **kwargs) -> str:
        """Read the contents of a file asynchronously."""
        params = _coerce_params(args, kwargs, positional_key="file_path")
        _ensure_required(params, ["file_path"])
        return await self.file_tools.read_file(params["file_path"])


class WriteFileTool(BaseTool):
    """Tool for writing files."""
    name: str = "write_file"
    description: str = "Writes content to a specified file. Input is 'file_path' (string) for the target file and 'content' (string) to write. Returns 'Success' or 'Failed'."

    class InputSchema(BaseModel):
        file_path: str = Field(..., description="The path to the file to write")
        content: str = Field(..., description="The content to write to the file")

    args_schema = InputSchema
    file_tools: FileTools
    
    def __init__(self, file_tools: FileTools, **kwargs):
        super().__init__(file_tools=file_tools, **kwargs)
    
    def _run(self, *args, **kwargs) -> str:
        """Write content to a file."""
        params = _coerce_params(args, kwargs)
        _ensure_required(params, ["file_path", "content"])
        success = _run_coroutine_sync(
            self.file_tools.write_file(params["file_path"], params["content"])
        )
        return "Success" if success else "Failed"
    
    async def _arun(self, *args, **kwargs) -> str:
        """Write content to a file asynchronously."""
        params = _coerce_params(args, kwargs)
        _ensure_required(params, ["file_path", "content"])
        success = await self.file_tools.write_file(params["file_path"], params["content"])
        return "Success" if success else "Failed"


class ListFilesTool(BaseTool):
    """Tool for listing files."""
    name: str = "list_files"
    description: str = "Lists files in a given directory. Input is 'directory' (optional string, defaults to current working directory) and 'pattern' (optional string, glob pattern like '*.py', defaults to '*' for all files). Returns a JSON string of a list of file paths."

    class InputSchema(BaseModel):
        directory: Optional[str] = Field(None, description="The directory to list files from. Defaults to current working directory.")
        pattern: str = Field("*", description="Glob pattern to filter files (e.g., '*.py', 'src/**/*.js'). Defaults to '*' (all files).")

    args_schema = InputSchema
    file_tools: FileTools
    
    def __init__(self, file_tools: FileTools, **kwargs):
        super().__init__(file_tools=file_tools, **kwargs)
    
    def _run(self, *args, **kwargs) -> str:
        """List files in a directory."""
        params = _coerce_params(args, kwargs, defaults={"directory": "", "pattern": "*"})
        files = _run_coroutine_sync(
            self.file_tools.list_files(params.get('directory', ""), params.get('pattern', "*"))
        )
        return json.dumps(files)
    
    async def _arun(self, *args, **kwargs) -> str:
        """List files in a directory asynchronously."""
        params = _coerce_params(args, kwargs, defaults={"directory": "", "pattern": "*"})
        files = await self.file_tools.list_files(params.get('directory', ""), params.get('pattern', "*"))
        return json.dumps(files)


class RunCommandTool(BaseTool):
    """Tool for running shell commands."""
    name: str = "run_command"
    description: str = "Executes a shell command. Input is 'command' (string) to run and 'cwd' (optional string, current working directory, defaults to project root). Returns a JSON string with 'exit_code', 'stdout', and 'stderr'."

    class InputSchema(BaseModel):
        command: str = Field(..., description="The shell command to run")
        cwd: Optional[str] = Field(None, description="The current working directory for the command. Defaults to project root.")

    args_schema = InputSchema
    file_tools: FileTools
    
    def __init__(self, file_tools: FileTools, **kwargs):
        super().__init__(file_tools=file_tools, **kwargs)
    
    def _run(self, *args, **kwargs) -> str:
        """Run a shell command."""
        params = _coerce_params(args, kwargs, positional_key="command")
        _ensure_required(params, ["command"])
        command = params["command"]
        _validate_shell_command(command)
        exit_code, stdout, stderr = _run_coroutine_sync(
            self.file_tools.run_command(command, params.get('cwd', ""))
        )
        return json.dumps({
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr
        })
    
    async def _arun(self, *args, **kwargs) -> str:
        """Run a shell command asynchronously."""
        params = _coerce_params(args, kwargs, positional_key="command")
        _ensure_required(params, ["command"])
        command = params["command"]
        _validate_shell_command(command)
        exit_code, stdout, stderr = await self.file_tools.run_command(command, params.get('cwd', ""))
        return json.dumps({
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr
        })


class AnalyzeProjectTool(BaseTool):
    """Tool for analyzing project structure."""
    name: str = "analyze_project"
    description: str = "Analyzes the project structure, identifies components, classes, functions, and dependencies. Input is 'project_path' (optional string, defaults to agent's configured project path). Returns a JSON string containing detailed project analysis."

    class InputSchema(BaseModel):
        project_path: Optional[str] = Field(None, description="The path to the project to analyze. Defaults to the agent's configured project path.")

    args_schema = InputSchema
    analyzer: ProjectAnalyzer
    
    def __init__(self, analyzer: ProjectAnalyzer, **kwargs):
        super().__init__(analyzer=analyzer, **kwargs)
        self.analyzer = analyzer
    
    def _run(self, *args, **kwargs) -> str:
        """Analyze the project structure."""
        analysis = self.analyzer.analyze_project()
        return json.dumps(analysis)
    
    async def _arun(self, *args, **kwargs) -> str:
        """Analyze the project structure asynchronously."""
        analysis = self.analyzer.analyze_project()
        return json.dumps(analysis)


class GenerateTestsTool(BaseTool):
    """Tool for generating tests."""
    name: str = "generate_tests"
    description: str = "Generates test files based on a provided project analysis. Input is 'project_analysis' (JSON string from analyze_project tool) and 'output_dir' (optional string, directory to save tests, defaults to 'tests'). Returns a JSON string mapping source files to generated test files."

    class InputSchema(BaseModel):
        project_analysis: str = Field(..., description="JSON string of the project analysis, typically obtained from the analyze_project tool.")
        output_dir: Optional[str] = Field("tests", description="Directory to save generated tests. Defaults to 'tests'.")

    args_schema = InputSchema
    test_generator: TestGenerator
    
    def __init__(self, test_generator: TestGenerator, **kwargs):
        super().__init__(test_generator=test_generator, **kwargs)
        self.test_generator = test_generator
    
    def _run(self, *args, **kwargs) -> str:
        """Generate tests for the project."""
        try:
            params = _coerce_params(args, kwargs)
            _ensure_required(params, ["project_analysis"])
            analysis = json.loads(params['project_analysis'])
            output_dir = params.get('output_dir', 'tests')
            tests = self.test_generator.generate_tests(analysis, output_dir)
            return json.dumps(tests)
        except Exception as e:
            raise RuntimeError(f"Error generating tests: {e}")
    
    async def _arun(self, *args, **kwargs) -> str:
        """Generate tests for the project asynchronously."""
        try:
            params = _coerce_params(args, kwargs)
            _ensure_required(params, ["project_analysis"])
            analysis = json.loads(params['project_analysis'])
            output_dir = params.get('output_dir', 'tests')
            tests = self.test_generator.generate_tests(analysis, output_dir)
            return json.dumps(tests)
        except Exception as e:
            raise RuntimeError(f"Error generating tests: {e}")


class RunTestsTool(BaseTool):
    """Tool for running tests."""
    name: str = "run_tests"
    description: str = "Runs tests for the project and collects results. Input is 'test_paths' (optional JSON string of a list of specific test file paths). If not provided, all detected tests will be run. Returns a JSON string with test results summary and details."

    class InputSchema(BaseModel):
        test_paths: Optional[str] = Field(None, description="JSON string of a list of specific test file paths to run. If not provided, all detected tests will be run.")

    args_schema = InputSchema
    test_runner: TestRunner
    
    def __init__(self, test_runner: TestRunner, **kwargs):
        super().__init__(test_runner=test_runner, **kwargs)
        self.test_runner = test_runner
    
    def _run(self, *args, **kwargs) -> str:
        """Run tests and collect results."""
        try:
            params = _coerce_params(args, kwargs)
            test_paths_param = params.get('test_paths')
            paths = json.loads(test_paths_param) if test_paths_param else None
            results = _run_coroutine_sync(self.test_runner.run_tests(paths))
            return json.dumps(results)
        except Exception as e:
            raise RuntimeError(f"Error running tests: {e}")
    
    async def _arun(self, *args, **kwargs) -> str:
        """Run tests and collect results asynchronously."""
        try:
            params = _coerce_params(args, kwargs)
            test_paths_param = params.get('test_paths')
            paths = json.loads(test_paths_param) if test_paths_param else None
            results = await self.test_runner.run_tests(paths)
            return json.dumps(results)
        except Exception as e:
            raise RuntimeError(f"Error running tests: {e}")


class GenerateReportTool(BaseTool):
    """Tool for generating test reports."""
    name: str = "generate_report"
    description: str = "Generates an HTML test report from aggregated test results. Input is 'test_results' (JSON string of aggregated test results from run_tests tool) and 'output_file' (optional string, path for the HTML report, defaults to 'test_report.html'). Returns the absolute path to the generated report file."

    class InputSchema(BaseModel):
        test_results: str = Field(..., description="JSON string of the aggregated test results, typically obtained from the run_tests tool.")
        output_file: Optional[str] = Field("test_report.html", description="Path to the output HTML report file. Defaults to 'test_report.html'.")

    args_schema = InputSchema
    aggregator: ResultsAggregator
    
    def __init__(self, aggregator: ResultsAggregator, **kwargs):
        super().__init__(aggregator=aggregator, **kwargs)
    
    def _run(self, *args, **kwargs) -> str:
        """Generate a test report."""
        try:
            params = _coerce_params(args, kwargs)
            _ensure_required(params, ["test_results"])
            results = json.loads(params['test_results'])
            output_file = params.get('output_file', "test_report.html")
            report_path = self.aggregator.generate_report(results, output_file)
            return json.dumps({"report_path": report_path})
        except Exception as e:
            raise RuntimeError(f"Error generating report: {e}")

    async def _arun(self, *args, **kwargs) -> str:
        """Generate a test report asynchronously."""
        try:
            params = _coerce_params(args, kwargs)
            _ensure_required(params, ["test_results"])
            results = json.loads(params['test_results'])
            output_file = params.get('output_file', "test_report.html")
            report_path = self.aggregator.generate_report(results, output_file)
            return json.dumps({"report_path": report_path})
        except Exception as e:
            raise RuntimeError(f"Error generating report: {e}")
