import json
from typing import Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ..explorer.file_tools import FileTools
from ..explorer.analyzer import ProjectAnalyzer
from ..generator.test_generator import TestGenerator
from ..executor.test_runner import TestRunner
from ..reporting.aggregator import ResultsAggregator


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
        import asyncio
        return asyncio.run(self.file_tools.read_file(kwargs['file_path']))
    
    async def _arun(self, *args, **kwargs) -> str:
        """Read the contents of a file asynchronously."""
        return await self.file_tools.read_file(kwargs['file_path'])


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
        import asyncio
        success = asyncio.run(self.file_tools.write_file(kwargs['file_path'], kwargs['content']))
        return "Success" if success else "Failed"
    
    async def _arun(self, *args, **kwargs) -> str:
        """Write content to a file asynchronously."""
        success = await self.file_tools.write_file(kwargs['file_path'], kwargs['content'])
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
        import asyncio
        files = asyncio.run(self.file_tools.list_files(kwargs.get('directory', ""), kwargs.get('pattern', "*")))
        return json.dumps(files)
    
    async def _arun(self, *args, **kwargs) -> str:
        """List files in a directory asynchronously."""
        files = await self.file_tools.list_files(kwargs.get('directory', ""), kwargs.get('pattern', "*"))
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
        import asyncio
        exit_code, stdout, stderr = asyncio.run(self.file_tools.run_command(kwargs['command'], kwargs.get('cwd', "")))
        return json.dumps({
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr
        })
    
    async def _arun(self, *args, **kwargs) -> str:
        """Run a shell command asynchronously."""
        exit_code, stdout, stderr = await self.file_tools.run_command(kwargs['command'], kwargs.get('cwd', ""))
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
            analysis = json.loads(kwargs['project_analysis'])
            tests = self.test_generator.generate_tests(analysis, kwargs.get('output_dir', 'tests'))
            return json.dumps(tests)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def _arun(self, *args, **kwargs) -> str:
        """Generate tests for the project asynchronously."""
        try:
            analysis = json.loads(kwargs['project_analysis'])
            tests = self.test_generator.generate_tests(analysis, kwargs.get('output_dir', 'tests'))
            return json.dumps(tests)
        except Exception as e:
            return json.dumps({"error": str(e)})


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
            import asyncio
            paths = json.loads(kwargs.get('test_paths', "[]")) if kwargs.get('test_paths') else None
            results = asyncio.run(self.test_runner.run_tests(paths))
            return json.dumps(results)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def _arun(self, *args, **kwargs) -> str:
        """Run tests and collect results asynchronously."""
        try:
            paths = json.loads(kwargs.get('test_paths', "[]")) if kwargs.get('test_paths') else None
            results = await self.test_runner.run_tests(paths)
            return json.dumps(results)
        except Exception as e:
            return json.dumps({"error": str(e)})


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
            results = json.loads(kwargs['test_results'])
            report_path = self.aggregator.generate_report(results, kwargs.get('output_file', "test_report.html"))
            return json.dumps({"report_path": report_path})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def _arun(self, *args, **kwargs) -> str:
        """Generate a test report asynchronously."""
        try:
            results = json.loads(kwargs['test_results'])
            report_path = self.aggregator.generate_report(results, kwargs.get('output_file', "test_report.html"))
            return json.dumps({"report_path": report_path})
        except Exception as e:
            return json.dumps({"error": str(e)})