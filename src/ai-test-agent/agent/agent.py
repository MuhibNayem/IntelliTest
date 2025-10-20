import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Union
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.tools import Tool
from langchain.memory import ConversationBufferMemory
from langchain_community.llms import Ollama
from langchain_core.prompts import StringPromptTemplate
from langchain_core.prompts import ChatPromptTemplate

from ..explorer.parser import CodeParser
from ..explorer.analyzer import ProjectAnalyzer
from ..explorer.file_tools import FileTools
from ..generator.test_generator import TestGenerator
from ..generator.data_generator import TestDataGenerator
from ..executor.test_runner import TestRunner
from ..reporting.aggregator import ResultsAggregator
from .tools import (
    ReadFileTool,
    WriteFileTool,
    ListFilesTool,
    RunCommandTool,
    AnalyzeProjectTool,
    GenerateTestsTool,
    RunTestsTool,
    GenerateReportTool
)
from .prompts import CUSTOM_PROMPT

class TestAutomationAgent:
    """Main agent for test automation."""
    
    def __init__(self, model_name: str = "gpt-oss-20b", project_path: str = None):
        self.model_name = model_name
        self.project_path = Path(project_path) if project_path else Path.cwd()
        
        # Initialize components
        self.llm = Ollama(model=model_name)
        self.parser = CodeParser()
        self.analyzer = ProjectAnalyzer(str(self.project_path))
        self.file_tools = FileTools(str(self.project_path))
        self.test_generator = TestGenerator(model_name)
        self.data_generator = TestDataGenerator()
        self.test_runner = TestRunner(str(self.project_path))
        self.results_aggregator = ResultsAggregator()
        
        # Initialize tools
        self.tools = self._initialize_tools()
        
        # Initialize agent
        self.agent_executor = self._initialize_agent()
        
        # Initialize memory
        self.memory = ConversationBufferMemory(memory_key="chat_history")
    
    def _initialize_tools(self) -> List[Tool]:
        """Initialize the tools for the agent."""
        return [
            ReadFileTool(self.file_tools),
            WriteFileTool(self.file_tools),
            ListFilesTool(self.file_tools),
            RunCommandTool(self.file_tools),
            AnalyzeProjectTool(self.analyzer),
            GenerateTestsTool(self.test_generator),
            RunTestsTool(self.test_runner),
            GenerateReportTool(self.results_aggregator)
        ]
    
    def _initialize_agent(self) -> AgentExecutor:
        """Initialize the agent."""
        # Create the agent prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", CUSTOM_PROMPT),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        # Create the agent
        agent = create_react_agent(self.llm, self.tools, prompt)

        # Create the agent executor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            memory=self.memory
        )

        return agent_executor

    def run(self, input_text: str) -> Dict:
        """Run the agent with the given input."""
        try:
            result = self.agent_executor.invoke({"input": input_text})
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def analyze_project(self) -> Dict:
        """Analyze the project structure."""
        try:
            analysis = self.analyzer.analyze_project()
            return {"success": True, "analysis": analysis}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_tests(self, output_dir: str = "tests") -> Dict:
        """Generate tests for the project."""
        try:
            # First analyze the project
            analysis_result = self.analyze_project()
            if not analysis_result["success"]:
                return analysis_result
            
            # Generate tests
            test_result = self.test_generator.generate_tests(
                analysis_result["analysis"],
                output_dir
            )
            
            return {"success": True, "tests": test_result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def run_tests(self, test_paths: List[str] = None) -> Dict:
        """Run tests and return results."""
        try:
            import asyncio
            results = asyncio.run(self.test_runner.run_tests(test_paths))
            return {"success": True, "results": results}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_report(self, test_results: Dict = None, output_file: str = "test_report.html") -> Dict:
        """Generate a test report."""
        try:
            if test_results is None:
                # Run tests first
                test_run_result = self.run_tests()
                if not test_run_result["success"]:
                    return test_run_result
                test_results = test_run_result["results"]
            
            # Generate report
            report_path = self.results_aggregator.generate_report(
                test_results,
                output_file
            )
            
            return {"success": True, "report_path": report_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

