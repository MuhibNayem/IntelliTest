import json
from typing import Any, Dict, List, Optional, Union
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ..explorer.file_tools import FileTools
from ..explorer.analyzer import ProjectAnalyzer
from ..generator.test_generator import TestGenerator
from ..executor.test_runner import TestRunner
from ..reporting.aggregator import ResultsAggregator


class ReadFileTool(BaseTool):
    """Tool for reading files."""
    name = "read_file"
    description = "Read the contents of a file"
    
    def __init__(self, file_tools: FileTools):
        super().__init__()
        self.file_tools = file_tools
    
    def _run(self, *args, **kwargs) -> str:
        """Read the contents of a file."""
        import asyncio
        return asyncio.run(self.file_tools.read_file(kwargs['file_path']))
    
    async def _arun(self, *args, **kwargs) -> str:
        """Read the contents of a file asynchronously."""
        return await self.file_tools.read_file(kwargs['file_path'])


class WriteFileTool(BaseTool):
    """Tool for writing files."""
    name = "write_file"
    description = "Write content to a file"
    
    def __init__(self, file_tools: FileTools):
        super().__init__()
        self.file_tools = file_tools
    
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
    name = "list_files"
    description = "List files in a directory"
    
    def __init__(self, file_tools: FileTools):
        super().__init__()
        self.file_tools = file_tools
    
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
    name = "run_command"
    description = "Run a shell command"
    
    def __init__(self, file_tools: FileTools):
        super().__init__()
        self.file_tools = file_tools
    
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
    name = "analyze_project"
    description = "Analyze the project structure and identify components"
    
    def __init__(self, analyzer: ProjectAnalyzer):
        super().__init__()
        self.analyzer = analyzer
    
    def _run(self, *args, **kwargs) -> str:
        """Analyze the project structure."""
        analysis = self.analyzer.analyze_project(kwargs.get('project_path', ""))
        return json.dumps(analysis)
    
    async def _arun(self, *args, **kwargs) -> str:
        """Analyze the project structure asynchronously."""
        analysis = self.analyzer.analyze_project(kwargs.get('project_path', ""))
        return json.dumps(analysis)


class GenerateTestsTool(BaseTool):
    """Tool for generating tests."""
    name = "generate_tests"
    description = "Generate tests for the project"
    
    def __init__(self, test_generator: TestGenerator):
        super().__init__()
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
    name = "run_tests"
    description = "Run tests and collect results"
    
    def __init__(self, test_runner: TestRunner):
        super().__init__()
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
    name = "generate_report"
    description = "Generate a test report"
    
    def __init__(self, aggregator: ResultsAggregator):
        super().__init__()
        self.aggregator = aggregator
    
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