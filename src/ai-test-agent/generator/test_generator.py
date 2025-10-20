import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from jinja2 import Environment, FileSystemLoader, Template
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain.chains.llm import LLMChain

class TestGenerator:
    """Generate test cases based on code analysis."""
    
    def __init__(self, model_name: str = "gpt-oss-20b"):
        self.model_name = model_name
        self.llm = Ollama(model=model_name)
        self.templates_dir = Path(__file__).parent / "templates"
        self.env = Environment(loader=FileSystemLoader(self.templates_dir))

    

    
    def generate_tests(self, project_analysis: Dict, output_dir: str = "tests") -> Dict:
        """Generate test files based on project analysis."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        generated_tests = {}
        
        for file_path, file_info in project_analysis.get("files", {}).items():
            # Skip test files
            if "test" in file_path.lower():
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
                continue  # Skip unsupported languages
            
            # Enhance file info with AI-generated descriptions
            enhanced_info = self._enhance_with_ai(file_info)
            
            # Generate test file content
            template = self.env.get_template(template_name)
            test_content = template.render(**enhanced_info)
            
            # Determine output file path
            relative_path = Path(file_path).relative_to(project_analysis.get("project_path", ""))
            test_file_name = relative_path.stem + test_extension
            test_file_path = output_path / test_file_name
            
            # Create subdirectories if needed
            test_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write test file
            with open(test_file_path, "w") as f:
                f.write(test_content)
            
            generated_tests[file_path] = str(test_file_path)
        
        return {
            "generated_tests": generated_tests,
            "output_dir": str(output_path)
        }
    
    def _enhance_with_ai(self, file_info: Dict) -> Dict:
        """Use AI to enhance file information with descriptions and expected behaviors."""
        enhanced_info = file_info.copy()
        
        # Enhance classes
        for cls in enhanced_info.get("classes", []):
            for method in cls.get("methods", []):
                # Generate description and expected behavior for each method
                method_info = self._generate_method_info(
                    cls["name"],
                    method["name"],
                    method.get("parameters", [])
                )
                method.update(method_info)
        
        # Enhance functions
        for func in enhanced_info.get("functions", []):
            # Generate description and expected behavior for each function
            func_info = self._generate_function_info(
                func["name"],
                func.get("parameters", [])
            )
            func.update(func_info)
        
        return enhanced_info
    
    def _generate_method_info(self, class_name: str, method_name: str, parameters: List[Dict]) -> Dict:
        """Generate method information using AI."""
        prompt = f"""
        Given a class named "{class_name}" with a method named "{method_name}" that takes the following parameters:
        {json.dumps(parameters, indent=2)}
        
        Generate a brief description of what this method likely does, and what its expected inputs and outputs might be.
        Return your response as a JSON object with the following keys:
        - description: A brief description of the method's purpose
        - inputs: Description of expected inputs
        - outputs: Description of expected outputs
        """
        
        try:
            response = self.llm(prompt)
            # Try to parse the response as JSON
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # If parsing fails, return a default response
                return {
                    "description": f"Execute {method_name} method",
                    "inputs": "Parameters as defined",
                    "outputs": "Method return value"
                }
        except Exception as e:
            print(f"Error generating method info: {e}")
            return {
                "description": f"Execute {method_name} method",
                "inputs": "Parameters as defined",
                "outputs": "Method return value"
            }
    
    def _generate_function_info(self, function_name: str, parameters: List[Dict]) -> Dict:
        """Generate function information using AI."""
        prompt = f"""
        Given a function named "{function_name}" that takes the following parameters:
        {json.dumps(parameters, indent=2)}
        
        Generate a brief description of what this function likely does, and what its expected inputs and outputs might be.
        Return your response as a JSON object with the following keys:
        - description: A brief description of the function's purpose
        - inputs: Description of expected inputs
        - outputs: Description of expected outputs
        """
        
        try:
            response = self.llm(prompt)
            # Try to parse the response as JSON
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # If parsing fails, return a default response
                return {
                    "description": f"Execute {function_name} function",
                    "inputs": "Parameters as defined",
                    "outputs": "Function return value"
                }
        except Exception as e:
            print(f"Error generating function info: {e}")
            return {
                "description": f"Execute {function_name} function",
                "inputs": "Parameters as defined",
                "outputs": "Function return value"
            }
    
    def generate_test_cases(self, function_info: Dict) -> Dict:
        """Generate specific test cases for a function."""
        prompt = f"""
        Given the following function information:
        {json.dumps(function_info, indent=2)}
        
        Generate test cases for this function, including:
        1. Positive test cases (normal operation)
        2. Negative test cases (error conditions)
        3. Edge cases (boundary values)
        
        Return your response as a JSON object with the following structure:
        {{
            "positive": [
                {{
                    "description": "Test case description",
                    "inputs": {{ "param1": "value1", "param2": "value2" }},
                    "expected": "expected output"
                }}
            ],
            "negative": [
                {{
                    "description": "Test case description",
                    "inputs": {{ "param1": "value1", "param2": "value2" }},
                    "expected": "expected error or output"
                }}
            ],
            "edge": [
                {{
                    "description": "Test case description",
                    "inputs": {{ "param1": "value1", "param2": "value2" }},
                    "expected": "expected output"
                }}
            ]
        }}
        """
        
        try:
            response = self.llm(prompt)
            # Try to parse the response as JSON
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # If parsing fails, return a default response
                return {
                    "positive": [{"description": "Basic functionality test", "inputs": {}, "expected": "Expected output"}],
                    "negative": [{"description": "Error condition test", "inputs": {}, "expected": "Expected error"}],
                    "edge": [{"description": "Boundary value test", "inputs": {}, "expected": "Expected output"}]
                }
        except Exception as e:
            print(f"Error generating test cases: {e}")
            return {
                "positive": [{"description": "Basic functionality test", "inputs": {}, "expected": "Expected output"}],
                "negative": [{"description": "Error condition test", "inputs": {}, "expected": "Expected error"}],
                "edge": [{"description": "Boundary value test", "inputs": {}, "expected": "Expected output"}]
            }