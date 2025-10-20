import ast
import json
import logging
import re
import aiofiles
from pathlib import Path
from typing import Any, Dict, Union
from jinja2 import Environment, FileSystemLoader
from langchain_community.llms import Ollama
from ..config import Settings, settings
from .data_generator import TestDataGenerator

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

class TestGenerator:
    """Generate test cases based on code analysis."""
    
    def __init__(self, llm_model_name: str = settings.llm_model_name, settings_obj: Settings = settings):
        self.settings = settings_obj
        self.llm = Ollama(model=llm_model_name)
        self.templates_dir = Path(__file__).parent / "templates"
        self.env = Environment(loader=FileSystemLoader(self.templates_dir))
        self.data_generator = TestDataGenerator()
        self.logger = logging.getLogger(__name__)

    
    def generate_tests(self, project_analysis: Dict, output_dir: str = str(settings.tests_output_dir)) -> Dict:
        """Generate test files based on project analysis."""
        self.logger.debug("output_dir: %s", output_dir)
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            output_path = self.settings.project_root / output_path
        output_path.mkdir(parents=True, exist_ok=True)
        
        generated_tests = {}
        
        for file_path, file_info in project_analysis.get("files", {}).items():
            # Skip test files
            if "test" in file_path.lower() and re.search(r"test[_\.\-]?", Path(file_path).stem, re.IGNORECASE):
                continue
            # Determine language and template
            language = file_info.get("language", "")
            if language == ".py":
                template_name = "python_test.j2"
                test_extension = "_test.py"
            elif language in [".js", ".jsx", ".ts", ".tsx"]:
                template_name = "javascript_test.j2"
                test_extension = ".test.js"
            elif language == ".java":
                template_name = "java_test.j2"
                test_extension = "Test.java"
            else:
                self.logger.debug("Skipping unsupported language '%s' for %s", language, file_path)
                continue  # Skip unsupported languages
            
            # Enhance file info with AI-generated descriptions and test cases
            enhanced_info = self._enhance_with_ai(file_info)
            
            # Generate test file content
            template = self.env.get_template(template_name)
            test_content = template.render(**enhanced_info)
            
            # Determine output file path
            project_root = Path(project_analysis.get("project_path", ""))
            try:
                relative_path = Path(file_path).relative_to(project_root)
                test_file_dir = output_path / relative_path.parent
                test_file_name = relative_path.stem + test_extension
            except ValueError:
                relative_path = Path(file_path).name
                test_file_dir = output_path
                test_file_name = Path(file_path).stem + test_extension
            test_file_dir.mkdir(parents=True, exist_ok=True)
            test_file_path = test_file_dir / test_file_name
            
            # Write test file
            with open(test_file_path, "w") as f:
                f.write(test_content)
            
            generated_tests[file_path] = str(test_file_path)
        
        return {
            "generated_tests": generated_tests,
            "output_dir": str(output_path)
        }
    
    def _enhance_with_ai(self, file_info: Dict) -> Dict:
        """Use AI to enhance file information with descriptions and test cases."""
        enhanced_info = file_info.copy()
        
        # Enhance classes
        for cls in enhanced_info.get("classes", []):
            for method in cls.get("methods", []):
                method_info = self._generate_method_info(
                    cls["name"],
                    method
                )
                method.update(method_info)
        
        # Enhance functions
        for func in enhanced_info.get("functions", []):
            func_info = self._generate_function_info(func)
            func.update(func_info)
        
        return enhanced_info
    
    def _generate_method_info(self, class_name: str, method: Dict) -> Dict:
        """Generate method information using AI."""
        return self.generate_test_cases(method, class_name)

    def _generate_function_info(self, func: Dict) -> Dict:
        """Generate function information using AI."""
        return self.generate_test_cases(func)

    def generate_test_cases(self, function_info: Dict, class_name: Union[str, None] = None) -> Dict:
        """Generate specific test cases for a function or method."""
        
        self.logger.info("Generating test cases for function/method: %s", function_info.get("name", "<unknown>"))
        
        # Prepare context for the prompt
        func_name = function_info["name"]
        context = {
            "function_name": func_name,
            "parameters": function_info.get("parameters", []),
            "source_code": function_info.get("source_code", ""), # Assuming source is added to function_info
            "docstring": function_info.get("docstring", ""), # Assuming docstring is added
        }
        if class_name:
            context["class_name"] = class_name

        # Generate diverse input data
        inputs = {}
        for param in context["parameters"]:
            param_name = param["name"]
            param_type = param.get("type", "string")
            inputs[param_name] = self.data_generator.generate_data(param_type, param_name)

        # Few-shot examples
        few_shot_examples = """
        Here are some examples of how to generate test cases:

        **Example 1: Simple function**
        ```json
        {
            "function_name": "add",
            "parameters": [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
            "source_code": "def add(a, b): return a + b"
        }
        ```
        **Generated Test Cases:**
        ```json
        {
            "positive": [
                {"description": "Test with two positive integers", "inputs": {"a": 2, "b": 3}, "expected": 5, "assertion": "assertEqual"}
            ],
            "negative": [
                {"description": "Test with a string and an integer", "inputs": {"a": "2", "b": 3}, "expected": "TypeError", "assertion": "assertRaises"}
            ],
            "edge": [
                {"description": "Test with zero", "inputs": {"a": 0, "b": 0}, "expected": 0, "assertion": "assertEqual"}
            ]
        }
        ```
        """

        prompt = f"""
        Given the following function information:
        {json.dumps(context, indent=2)}

        And the following generated input data:
        {json.dumps(inputs, indent=2)}

        {few_shot_examples}

        Generate test cases for this function, including:
        1. Positive test cases (normal operation)
        2. Negative test cases (error conditions)
        3. Edge cases (boundary values)

        For each test case, provide a description, the inputs, the expected output, and the type of assertion to use (e.g., "assertEqual", "assertTrue", "assertRaises").

        Return your response as a JSON object with the following structure:
        {{
            "positive": [
                {{
                    "description": "Test case description",
                    "inputs": {{ "param1": "value1" }},
                    "expected": "expected output",
                    "assertion": "assertion_type"
                }}
            ],
            "negative": [],
            "edge": []
        }}
        Generate structured test cases in pure JSON.
        Make sure:
        - All string values are double quoted
        - Exception names like TypeError are represented as strings, e.g. "TypeError"
        - Return strict JSON only, with no comments or explanations. Do not include //, # or any other wrong JSON syntax.
        Example output format:
        {{"positive": [...], "negative": [...], "edge": [...]}}
        
        """
        
        try:

            raw_response = self.llm.invoke(prompt)
            test_cases = self.safe_parse_ai_response(raw_response)
            return test_cases
        except Exception as e:
            self.logger.debug(f"Error generating test cases: {e}")
            return {"positive": [], "negative": [], "edge": []}
        
    def safe_parse_ai_response(self, raw_response: Any) -> Any:
        """Parses an LLM response into JSON-safe Python dict."""

        if isinstance(raw_response, str):
            response_text = raw_response.strip()
        elif hasattr(raw_response, "content"):
            response_text = raw_response.content.strip()
        else:
            response_text = json.dumps(raw_response)

        if "```" in response_text:
            match = re.search(r"```(?:json)?(.*?)```", response_text, re.DOTALL)
            if match:
                response_text = match.group(1).strip()
                
        response_text = re.sub(r"//.*?$", "", response_text, flags=re.MULTILINE)
        response_text = re.sub(r"#.*?$", "", response_text, flags=re.MULTILINE)


        response_text = re.sub(
            r'(?<!["\'])\b([A-Z][A-Za-z0-9_]*Error)\b(?!["\'])',
            r'"\1"',
            response_text
        )
        
        response_text = re.sub(r",(\s*[}\]])", r"\1", response_text)

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        try:
            return ast.literal_eval(response_text)
        except Exception:
            pass

        self.logger.warning("AI response could not be parsed as JSON: %s", response_text)
        return {"positive": [], "negative": [], "edge": []}

    async def apply_test_fix(self, test_file_path: Path, fix_suggestion: Dict) -> Dict:
        """Apply an AI-suggested fix to a test file."""
        try:
            # Read the current content of the test file
            async with aiofiles.open(test_file_path, "r") as f:
                current_content = await f.read()

            # Apply the fix based on the suggestion type
            modification_type = fix_suggestion.get("modification_type")
            
            if modification_type == "replace_code":
                old_code = fix_suggestion.get("old_code")
                new_code = fix_suggestion.get("new_code")
                if old_code and new_code:
                    updated_content = current_content.replace(old_code, new_code, 1) # Replace only first occurrence
                else:
                    return {"success": False, "error": "Missing old_code or new_code for replace_code modification."}
            elif modification_type == "add_line":
                line_number = fix_suggestion.get("line_number")
                line_to_add = fix_suggestion.get("line_to_add")
                if line_number is not None and line_to_add is not None:
                    lines = current_content.splitlines(keepends=True)
                    if 0 <= line_number < len(lines):
                        lines.insert(line_number, line_to_add + "\n")
                        updated_content = "".join(lines)
                    else:
                        return {"success": False, "error": f"Line number {line_number} out of bounds for add_line modification."}
                else:
                    return {"success": False, "error": "Missing line_number or line_to_add for add_line modification."}
            # Add more modification types as needed (e.g., "delete_line", "update_assertion")
            else:
                return {"success": False, "error": f"Unsupported modification type: {modification_type}"}

            # Write the updated content back to the file
            async with aiofiles.open(test_file_path, "w") as f:
                await f.write(updated_content)
            
            return {"success": True, "message": f"Successfully applied fix to {test_file_path}."}
        except Exception as e:
            return {"success": False, "error": f"Error applying fix to {test_file_path}: {e}"}
