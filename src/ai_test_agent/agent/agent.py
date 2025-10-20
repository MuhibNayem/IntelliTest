import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, TypedDict, Annotated, Union, cast, Tuple
from langchain.tools import BaseTool
from langchain_core.agents import AgentAction
from langchain_community.llms import Ollama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.exceptions import LangChainException
from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError
import re
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import click

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
from .prompts import (
    CUSTOM_PROMPT,
    ANALYZE_PROJECT_PROMPT,
    GENERATE_TESTS_PROMPT,
    RUN_TESTS_PROMPT,
    GENERATE_REPORT_PROMPT,
)
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
        self.llm = Ollama(model=llm_model_name)
        self.parser = parser or CodeParser()
        self.analyzer = analyzer or ProjectAnalyzer(str(self.project_path), self.parser)
        self.file_tools = file_tools or FileTools(str(self.project_path))
        self.test_generator = test_generator or TestGenerator(llm_model_name, self.settings)
        self.data_generator = data_generator or TestDataGenerator()
        self.test_runner = test_runner or TestRunner(str(self.project_path), self.settings)
        self.results_aggregator = results_aggregator or ResultsAggregator(self.settings)
        self._latest_analysis: Optional[Dict] = None
        
        # Initialize tools
        self.tools: List[BaseTool] = self._initialize_tools()
        self._tool_names_text = ", ".join(tool.name for tool in self.tools)
        self._tool_descriptions_text = self._format_tool_descriptions()
        self._prompt_template = CUSTOM_PROMPT.format(
            tools=self._tool_descriptions_text,
            tool_names=self._tool_names_text,
            input="{input}",
            agent_scratchpad="{agent_scratchpad}",
        )
        
        # Initialize memory saver for LangGraph
        self.memory_saver = MemorySaver()

        # Initialize agent
        self.agent = self._initialize_agent()
    
    def _initialize_tools(self) -> List[BaseTool]:
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
    
    def _format_tool_descriptions(self) -> str:
        """Build a descriptive list of tools with optional guidance."""
        guidance_map = {
            "AnalyzeProjectTool": ANALYZE_PROJECT_PROMPT.strip(),
            "GenerateTestsTool": GENERATE_TESTS_PROMPT.strip(),
            "RunTestsTool": RUN_TESTS_PROMPT.strip(),
            "GenerateReportTool": GENERATE_REPORT_PROMPT.strip(),
        }
        segments: List[str] = []
        for tool in self.tools:
            lines = [f"{tool.name}: {tool.description.strip()}"]
            guidance = guidance_map.get(tool.name)
            if guidance:
                lines.append(f"Guidance: {guidance}")
            segments.append("\n".join(lines))
        return "\n\n".join(segments)

    def _find_latest_user_message(self, messages: List[BaseMessage]) -> Tuple[Optional[int], Optional[HumanMessage]]:
        """Locate the most recent human message in the conversation history."""
        for index in range(len(messages) - 1, -1, -1):
            message = messages[index]
            if isinstance(message, HumanMessage):
                return index, message
        return None, None

    def _build_agent_scratchpad(self, messages: List[BaseMessage]) -> str:
        """Construct the agent scratchpad from previous actions and observations."""
        scratchpad_parts: List[str] = []
        for message in messages:
            if isinstance(message, AIMessage):
                if "action" in message.additional_kwargs:
                    action = message.additional_kwargs["action"]
                    if isinstance(action, AgentAction) and action.log:
                        scratchpad_parts.append(action.log.strip())
                else:
                    content = message.content
                    normalized = ""
                    if isinstance(content, str):
                        normalized = content.strip()
                    elif isinstance(content, list):
                        parts: List[str] = []
                        for item in content:
                            if isinstance(item, str):
                                parts.append(item.strip())
                            else:
                                try:
                                    parts.append(json.dumps(item))
                                except Exception:
                                    parts.append(str(item))
                        normalized = "\n".join(p for p in parts if p).strip()
                    elif isinstance(content, dict):
                        try:
                            normalized = json.dumps(content)
                        except Exception:
                            normalized = str(content)
                    else:
                        normalized = str(content)
                    if normalized:
                        scratchpad_parts.append(normalized)
        return "\n".join(part for part in scratchpad_parts if part).strip()

    @staticmethod
    def _escape_braces(text: str) -> str:
        """Escape braces so they survive subsequent string formatting."""
        return text.replace("{", "{{").replace("}", "}}")

    def _format_main_prompt(self, user_input: str, scratchpad: str) -> str:
        """Create the full prompt presented to the LLM."""
        sanitized_input = self._escape_braces(user_input.strip()) if user_input else ""
        scratchpad_content = scratchpad.strip()
        if scratchpad_content:
            scratchpad_content = f"{scratchpad_content}\nThought:"
        else:
            scratchpad_content = "Thought:"
        sanitized_scratchpad = self._escape_braces(scratchpad_content)
        return self._prompt_template.format(
            input=sanitized_input,
            agent_scratchpad=sanitized_scratchpad
        )

    def _parse_agent_output(self, llm_output: str) -> Union[AgentAction, Dict]:
        """Parse the LLM's output to extract an AgentAction or a final response."""
        # Use regex to parse the Action and Action Input
        action_pattern = r"Action:\s*(.*?)\s*Action Input:\s*(.*)"
        match = re.search(action_pattern, llm_output, re.DOTALL)

        if match:
            try:
                action = match.group(1).strip()
                action_input = match.group(2).strip()
                return AgentAction(tool=action, tool_input=action_input, log=llm_output)
            except Exception:
                pass # Fallback to treating as final answer
        
        return {"output": llm_output} # Treat as final answer

    def _agent_node(self, state: AgentState) -> Dict:
        """Agent node for LangGraph."""
        latest_user_index, latest_user_message = self._find_latest_user_message(state["messages"])
        if latest_user_message:
            content = latest_user_message.content
            if isinstance(content, str):
                user_input = content
            elif isinstance(content, (list, dict)):
                try:
                    user_input = json.dumps(content)
                except Exception:
                    user_input = str(content)
            else:
                user_input = str(content)
        else:
            user_input = ""
        if latest_user_index is not None:
            history_messages = state["messages"][:latest_user_index] + state["messages"][latest_user_index + 1:]
        else:
            history_messages = state["messages"]
        scratchpad = self._build_agent_scratchpad(history_messages)
        prompt = self._format_main_prompt(user_input, scratchpad)

        llm_output = self.llm.invoke([SystemMessage(content=prompt)])
        
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
        if isinstance(last_message, AIMessage):
            # Check if the AI message contains an action
            if "action" in last_message.additional_kwargs:
                return "continue" # Continue to tool node
            # Check if the AI message contains a final answer
            if "Final Answer:" in last_message.content:
                return "end" # End with final answer
        return "end" # Default to end if no action or final answer is detected

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
            user_message = HumanMessage(content=input_text)
            thread_id = "interactive_session"
            config = cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})
            result = self.agent.invoke({"messages": [user_message]}, config=config)
            last_ai_message = ""
            
            if "messages" in result and result["messages"]:
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage):
                        last_ai_message = msg.content
                        break
            
            return {"success": True, "result": last_ai_message}

        except (LangChainException, ValidationError) as e:
            return {"success": False, "error": f"Agent execution error: {e}"}
        except Exception as e:
            return {"success": False, "error": f"An unexpected error occurred: {e}"}
    
    def analyze_project(self) -> Dict:
        """Analyze the project structure."""
        try:
            analysis = self.analyzer.analyze_project()
            self._latest_analysis = analysis
            return {"success": True, "analysis": analysis}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_tests(self, output_dir: str = "tests") -> Dict:
        """Generate tests for the project."""
        try:
            if not self._latest_analysis:
                analysis_result = self.analyze_project()
                if not analysis_result["success"]:
                    return analysis_result
                analysis_data = analysis_result["analysis"]
            else:
                analysis_data = self._latest_analysis
            
            test_result = self.test_generator.generate_tests(
                analysis_data,
                output_dir
            )
            
            self.generated_tests_map = test_result["generated_tests"]
            self.test_runner.set_generated_tests_map(self.generated_tests_map)
            return {"success": True, "tests": test_result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _run_tests_async(self, test_paths: Optional[List[str]] = None) -> Dict:
        """Run tests asynchronously and wrap results."""
        try:
            results = await self.test_runner.run_tests(test_paths)
            return {"success": True, "results": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_tests(self, test_paths: Optional[List[str]] = None) -> Dict:
        """Run tests and return results, creating an event loop if necessary."""
        return asyncio.run(self._run_tests_async(test_paths))
    
    def generate_report(self, test_results: Dict, output_file: str = "test_report.html") -> Dict:
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

    def record_feedback(self, user_input: str, agent_response: str, feedback: str) -> Dict:
        """Record user feedback for agent's performance."""
        print(f"--- User Feedback Recorded ---")
        print(f"User Input: {user_input}")
        print(f"Agent Response: {agent_response}")
        print(f"Feedback: {feedback}")
        print(f"----------------------------")
        return {"success": True, "message": "Feedback recorded successfully."}

    async def debug_tests(self, max_iterations: int = 3) -> Dict:
        """Iteratively debug failed tests using AI suggestions."""
        click.echo("Starting AI-driven test debugging...")
        run_result = None
        for iteration in range(1, max_iterations + 1):
            click.echo(f"\n--- Debugging Iteration {iteration}/{max_iterations} ---")
            run_result = await self._run_tests_async()

            if run_result["success"] and run_result["results"]["summary"].get("failed", 0) == 0:
                click.echo("All tests passed after debugging.")
                return {"success": True, "message": "Tests successfully debugged.", "results": run_result["results"]}
            elif not run_result["success"]:
                click.echo(f"Error running tests: {run_result['error']}")
                return {"success": False, "error": f"Error running tests: {run_result['error']}"}

            failed_tests_info = self._extract_failed_test_info(run_result["results"])
            if not failed_tests_info:
                click.echo("No failed tests found, but overall run was not successful. Exiting debugging.")
                return {"success": False, "error": "No failed tests found, but overall run was not successful."}

            click.echo(f"Found {len(failed_tests_info)} failed tests. Attempting to suggest and apply fixes...")
            fix_suggestion_result = await self._ai_suggest_and_apply_fix(failed_tests_info)

            if not fix_suggestion_result["success"]:
                click.echo(f"AI failed to suggest/apply fixes: {fix_suggestion_result['error']}")
                return {"success": False, "error": f"AI failed to suggest/apply fixes: {fix_suggestion_result['error']}"}
            else:
                click.echo(f"AI suggested and applied fixes: {fix_suggestion_result['message']}")

        click.echo(f"Debugging finished after {max_iterations} iterations. Tests may still be failing.")
        return {"success": False, "error": "Tests still failing after maximum debugging iterations.", "results": run_result["results"] if run_result else None}

    def _extract_failed_test_info(self, test_results: Dict) -> List[Dict]:
        """Extract relevant information from failed tests."""
        failed_tests = []
        for suite in test_results.get("details", []):
            for test in suite.get("tests", []):
                if test.get("status") == "failed" or test.get("status") == "error":
                    failed_tests.append({
                        "name": test.get("name"),
                        "classname": test.get("classname"),
                        "message": test.get("message"),
                        "traceback": test.get("traceback"),
                        "framework": suite.get("framework"),
                        "test_file_path": test.get("test_file_path"),
                        "source_file_path": test.get("source_file_path")
                    })
        return failed_tests

    async def _ai_suggest_and_apply_fix(self, failed_tests_info: List[Dict]) -> Dict:
        """AI to suggest and apply fixes based on failed test info."""
        click.echo("AI is analyzing failed tests and suggesting fixes...")
        
        all_fixes_applied = True
        applied_fixes_details = []
        for failed_test in failed_tests_info:
            test_file_path = failed_test.get("test_file_path")
            source_file_path = failed_test.get("source_file_path")

            if not test_file_path:
                click.echo(f"Warning: No test_file_path found for failed test {failed_test.get('name')}. Skipping AI fix attempt.")
                all_fixes_applied = False
                continue

            try:
                test_code = await self.file_tools.read_file(test_file_path)
                source_code = ""
                if source_file_path:
                    source_code = await self.file_tools.read_file(source_file_path)

                prompt = f"""
                A test has failed. Analyze the following information and suggest a fix.

                --- Failed Test Details ---
                Test Name: {failed_test.get('name')}
                Class Name: {failed_test.get('classname')}
                Message: {failed_test.get('message')}
                Traceback: {failed_test.get('traceback')}
                Framework: {failed_test.get('framework')}

                --- Test File Content ({test_file_path}) ---
                ```
                {test_code}
                ```

                --- Source File Content ({source_file_path}) ---
                ```
                {source_code}
                ```

                Based on the above, identify the root cause of the failure and suggest a modification.
                The modification should be applied to the test file ({test_file_path}).
                
                Provide your suggestion in a JSON object with the following structure:
                {{
                    "success": true,
                    "reasoning": "Your reasoning for the fix.",
                    "file_to_modify": "{test_file_path}",
                    "modification_type": "replace_code" | "add_line" | "delete_line" | "update_assertion",
                    "details": {{
                        "old_code": "<exact code to replace>",
                        "new_code": "<new code>"
                    }} 
                    OR
                    "details": {{
                        "line_number": <0-indexed line number>,
                        "line_to_add": "<new line content>"
                    }}
                    OR
                    "details": {{
                        "line_number": <0-indexed line number>,
                        "num_lines_to_delete": <number of lines to delete>
                    }}
                    OR
                    "details": {{
                        "test_name": "<name of the test to modify>",
                        "assertion_type": "<new assertion type>",
                        "expected_value": "<new expected value>"
                    }}
                }}
                If you cannot determine a fix, set "success": false and provide a "reasoning".
                """
                
                llm_response = self.llm.invoke(prompt)
                fix_suggestion = json.loads(llm_response)

                if fix_suggestion.get("success") and fix_suggestion.get("file_to_modify") == test_file_path:
                    click.echo(f"AI suggested fix for {failed_test.get('name')}: {fix_suggestion.get('reasoning')}")
                    apply_result = await self.test_generator.apply_test_fix(Path(test_file_path), fix_suggestion.get("details"))
                    if not apply_result["success"]:
                        click.echo(f"Error applying fix: {apply_result['error']}")
                        all_fixes_applied = False
                        applied_fixes_details.append({"test": failed_test.get('name'), "status": "error_applying", "details": apply_result['error']})
                    else:
                        applied_fixes_details.append({"test": failed_test.get('name'), "status": "applied", "details": apply_result})
                else:
                    click.echo(f"AI could not suggest a valid fix for {failed_test.get('name')}: {fix_suggestion.get('reasoning', 'No valid suggestion.')}")
                    all_fixes_applied = False
                    applied_fixes_details.append({"test": failed_test.get('name'), "status": "not_applied", "reason": fix_suggestion.get('reasoning', 'No valid suggestion.')})

            except Exception as e:
                click.echo(f"Error during AI fix suggestion/application for {failed_test.get('name')}: {e}")
                all_fixes_applied = False
                applied_fixes_details.append({"test": failed_test.get('name'), "status": "error", "reason": str(e)})
        
        if all_fixes_applied:
            return {"success": True, "message": "All suggested fixes applied.", "fixes_applied": applied_fixes_details}
        else:
            return {"success": False, "error": "Some fixes could not be applied or suggested.", "fixes_applied": applied_fixes_details}
