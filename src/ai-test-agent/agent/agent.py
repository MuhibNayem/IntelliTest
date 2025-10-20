from pathlib import Path
from typing import Dict, List, Optional, TypedDict, Annotated, Union
from langchain_core.tools import Tool
from langchain_core.agents import AgentAction
from langchain_community.llms import ollama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

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
from ..config import Settings, settings

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]

class TestAutomationAgent:
    """Main agent for test automation."""
    
    def __init__(
        self,
        project_path: Optional[Path] = None,
        llm_model_name: str = settings.llm_model_name,
        parser: Optional[CodeParser] = None,
        analyzer: Optional[ProjectAnalyzer] = None,
        file_tools: Optional[FileTools] = None,
        test_generator: Optional[TestGenerator] = None,
        data_generator: Optional[TestDataGenerator] = None,
        test_runner: Optional[TestRunner] = None,
        results_aggregator: Optional[ResultsAggregator] = None,
        settings_obj: Settings = settings,
    ):
        self.settings = settings_obj
        self.project_path = project_path or self.settings.project_root
        
        # Initialize components with dependency injection
        self.llm = ollama(model=llm_model_name)
        self.parser = parser or CodeParser()
        self.analyzer = analyzer or ProjectAnalyzer(str(self.project_path), self.parser)
        self.file_tools = file_tools or FileTools(str(self.project_path))
        self.test_generator = test_generator or TestGenerator(llm_model_name)
        self.data_generator = data_generator or TestDataGenerator()
        self.test_runner = test_runner or TestRunner(str(self.project_path), self.settings)
        self.results_aggregator = results_aggregator or ResultsAggregator(self.settings)
        
        # Initialize tools
        self.tools = self._initialize_tools()
        
        # Initialize agent
        self.agent = self._initialize_agent()
        
        # Initialize memory saver for LangGraph
        self.memory_saver = MemorySaver()
    
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
    
    def _parse_agent_output(self, llm_output: str) -> Union[AgentAction, Dict]:
        """Parse the LLM's output to extract an AgentAction or a final response."""
        # This is a simplified parser. A more robust one would use regex or a structured output parser.
        if "Action:" in llm_output and "Action Input:" in llm_output:
            try:
                action_start = llm_output.find("Action:") + len("Action:")
                action_end = llm_output.find("Action Input:")
                action = llm_output[action_start:action_end].strip()

                action_input_start = action_end + len("Action Input:")
                action_input = llm_output[action_input_start:].strip()
                
                # Assuming tool names are simple strings
                return AgentAction(tool=action, tool_input=action_input, log=llm_output)
            except Exception:
                pass # Fallback to treating as final answer
        
        return {"output": llm_output} # Treat as final answer

    def _agent_node(self, state: AgentState) -> Dict:
        """Agent node for LangGraph."""
        # The LLM is invoked with the current messages and tools
        # It should output a thought, then an action or a final answer.
        llm_output = self.llm.invoke(state["messages"] + [HumanMessage(content=f"Available tools: {self.tools}")])
        
        parsed_output = self._parse_agent_output(llm_output.content)

        if isinstance(parsed_output, AgentAction):
            return {"messages": [AIMessage(content="", additional_kwargs={"action": parsed_output})]}
        else:
            return {"messages": [AIMessage(content=parsed_output["output"])]}

    def _tool_node(self, state: AgentState) -> Dict:
        """Tool node for LangGraph."""
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and "action" in last_message.additional_kwargs:
            action = last_message.additional_kwargs["action"]
            tool_name = action.tool
            tool_input = action.tool_input
            
            # Find and execute the tool
            for tool in self.tools:
                if tool.name == tool_name:
                    observation = tool.run(tool_input)
                    return {"messages": [AIMessage(content=f"Observation: {observation}")]}
            return {"messages": [AIMessage(content=f"Error: Tool {tool_name} not found.")]}
        return {"messages": [AIMessage(content="Error: No tool action found in last message.")]}

    def _should_continue(self, state: AgentState) -> str:
        """Decide whether to continue in the graph or end."""
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and "action" in last_message.additional_kwargs:
            return "continue" # Continue to tool node
        return "end" # End with final answer

    def _initialize_agent(self):
        """Initialize the agent using LangGraph."""
        # Define the graph
        workflow = StateGraph(AgentState)

        # Add the agent node
        workflow.add_node("agent", self._agent_node)

        # Add the tool node
        workflow.add_node("tools", self._tool_node)

        # Set the entry point
        workflow.set_entry_point("agent")

        # Add conditional edges
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        workflow.add_edge("tools", "agent") # After tool execution, go back to agent

        # Compile the graph with memory
        app = workflow.compile(checkpointer=self.memory_saver)
        return app

    def run(self, input_text: str) -> Dict:
        """Run the agent with the given input."""
        try:
            # LangGraph app expects a list of BaseMessage
            user_message = HumanMessage(content=input_text)
            
            # Use a fixed thread_id for now, or generate/manage dynamically
            # For interactive mode, a single thread_id is sufficient.
            thread_id = "interactive_session" 
            
            config = {"configurable": {"thread_id": thread_id}}
            
            # Invoke the compiled LangGraph app
            # The input is a dict with "messages" key, containing a list of BaseMessage
            result = self.agent.invoke({"messages": [user_message]}, config=config)
            
            # The result from LangGraph is typically a dict with a "messages" key
            # containing the updated list of messages.
            # We need to extract the last AI message.
            last_ai_message = ""
            if "messages" in result and result["messages"]:
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage):
                        last_ai_message = msg.content
                        break
            
            return {"success": True, "result": last_ai_message}
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

