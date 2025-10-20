import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import tree_sitter
from tree_sitter import Language, Parser

# Initialize parsers for different languages
Language.build_library(
    'build/my-languages.so',
    [
        'vendor/tree-sitter-python',
        'vendor/tree-sitter-javascript',
        'vendor/tree-sitter-java'
    ]
)

PY_LANGUAGE = Language('build/my-languages.so', 'python')
JS_LANGUAGE = Language('build/my-languages.so', 'javascript')
JAVA_LANGUAGE = Language('build/my-languages.so', 'java')

class CodeParser:
    """Parse code files to extract structure and information."""
    
    def __init__(self):
        self.parsers = {
            '.py': Parser(language=PY_LANGUAGE),
            '.js': Parser(language=JS_LANGUAGE),
            '.jsx': Parser(language=JS_LANGUAGE),
            '.ts': Parser(language=JS_LANGUAGE),
            '.tsx': Parser(language=JS_LANGUAGE),
            '.java': Parser(language=JAVA_LANGUAGE),
        }
    
    def parse_file(self, file_path: Union[str, Path]) -> Dict:
        """Parse a single file and extract its structure."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        extension = file_path.suffix.lower()
        if extension not in self.parsers:
            return {"error": f"Unsupported file type: {extension}"}
        
        parser = self.parsers[extension]
        with open(file_path, 'rb') as f:
            source_code = f.read()
        
        tree = parser.parse(bytes(source_code))
        
        result = {
            "file_path": str(file_path),
            "language": extension,
            "classes": [],
            "functions": [],
            "imports": [],
            "dependencies": []
        }
        
        # Extract classes, functions, imports based on language
        if extension in ['.py']:
            self._extract_python_info(tree, source_code, result)
        elif extension in ['.js', '.jsx', '.ts', '.tsx']:
            self._extract_js_info(tree, source_code, result)
        elif extension == '.java':
            self._extract_java_info(tree, source_code, result)
        
        return result
    
    def _extract_python_info(self, tree, source_code: bytes, result: Dict):
        """Extract information from Python code."""
        root_node = tree.root_node
        
        # Find classes
        class_nodes = []
        self._find_nodes_of_type(root_node, "class_definition", class_nodes)
        
        for node in class_nodes:
            class_name = self._get_node_text(node.child_by_field_name("name"), source_code)
            methods = []
            
            # Find methods within the class
            for child in node.children:
                if child.type == "block":
                    method_nodes = []
                    self._find_nodes_of_type(child, "function_definition", method_nodes)
                    
                    for method_node in method_nodes:
                        method_name = self._get_node_text(method_node.child_by_field_name("name"), source_code)
                        parameters = self._extract_parameters(method_node, source_code)
                        methods.append({
                            "name": method_name,
                            "parameters": parameters,
                            "line": method_node.start_point[0] + 1
                        })
            
            result["classes"].append({
                "name": class_name,
                "methods": methods,
                "line": node.start_point[0] + 1
            })
        
        # Find functions
        function_nodes = []
        self._find_nodes_of_type(root_node, "function_definition", function_nodes)
        
        for node in function_nodes:
            # Skip if inside a class (already captured)
            parent = node.parent
            while parent:
                if parent.type == "class_definition":
                    break
                parent = parent.parent
            else:  # Only add if not inside a class
                function_name = self._get_node_text(node.child_by_field_name("name"), source_code)
                parameters = self._extract_parameters(node, source_code)
                result["functions"].append({
                    "name": function_name,
                    "parameters": parameters,
                    "line": node.start_point[0] + 1
                })
        
        # Find imports
        import_nodes = []
        self._find_nodes_of_type(root_node, "import_statement", import_nodes)
        self._find_nodes_of_type(root_node, "import_from_statement", import_nodes)
        
        for node in import_nodes:
            import_text = self._get_node_text(node, source_code)
            result["imports"].append(import_text)
    
    def _extract_js_info(self, tree, source_code: bytes, result: Dict):
        """Extract information from JavaScript/TypeScript code."""
        root_node = tree.root_node
        
        # Find classes
        class_nodes = []
        self._find_nodes_of_type(root_node, "class_declaration", class_nodes)
        
        for node in class_nodes:
            class_name = self._get_node_text(node.child_by_field_name("name"), source_code)
            methods = []
            
            # Find methods within the class
            for child in node.children:
                if child.type == "class_body":
                    method_nodes = []
                    self._find_nodes_of_type(child, "method_definition", method_nodes)
                    
                    for method_node in method_nodes:
                        method_name = self._get_node_text(method_node.child_by_field_name("name"), source_code)
                        parameters = self._extract_parameters(method_node, source_code)
                        methods.append({
                            "name": method_name,
                            "parameters": parameters,
                            "line": method_node.start_point[0] + 1
                        })
            
            result["classes"].append({
                "name": class_name,
                "methods": methods,
                "line": node.start_point[0] + 1
            })
        
        # Find functions
        function_nodes = []
        self._find_nodes_of_type(root_node, "function_declaration", function_nodes)
        self._find_nodes_of_type(root_node, "arrow_function", function_nodes)
        
        for node in function_nodes:
            # Skip if inside a class (already captured)
            parent = node.parent
            while parent:
                if parent.type == "class_declaration":
                    break
                parent = parent.parent
            else:  # Only add if not inside a class
                if node.type == "function_declaration":
                    function_name = self._get_node_text(node.child_by_field_name("name"), source_code)
                else:  # arrow function
                    # Arrow functions might not have a name, use the variable they're assigned to
                    function_name = "anonymous"
                    if node.parent and node.parent.type == "variable_declarator":
                        function_name = self._get_node_text(node.parent.child_by_field_name("name"), source_code)
                
                parameters = self._extract_parameters(node, source_code)
                result["functions"].append({
                    "name": function_name,
                    "parameters": parameters,
                    "line": node.start_point[0] + 1
                })
        
        # Find imports
        import_nodes = []
        self._find_nodes_of_type(root_node, "import_statement", import_nodes)
        
        for node in import_nodes:
            import_text = self._get_node_text(node, source_code)
            result["imports"].append(import_text)
    
    def _extract_java_info(self, tree, source_code: bytes, result: Dict):
        """Extract information from Java code."""
        root_node = tree.root_node
        
        # Find classes
        class_nodes = []
        self._find_nodes_of_type(root_node, "class_declaration", class_nodes)
        
        for node in class_nodes:
            class_name = self._get_node_text(node.child_by_field_name("name"), source_code)
            methods = []
            
            # Find methods within the class
            for child in node.children:
                if child.type == "class_body":
                    method_nodes = []
                    self._find_nodes_of_type(child, "method_declaration", method_nodes)
                    
                    for method_node in method_nodes:
                        method_name = self._get_node_text(method_node.child_by_field_name("name"), source_code)
                        parameters = self._extract_parameters(method_node, source_code)
                        methods.append({
                            "name": method_name,
                            "parameters": parameters,
                            "line": method_node.start_point[0] + 1
                        })
            
            result["classes"].append({
                "name": class_name,
                "methods": methods,
                "line": node.start_point[0] + 1
            })
        
        # Find functions (methods outside classes)
        method_nodes = []
        self._find_nodes_of_type(root_node, "method_declaration", method_nodes)
        
        for node in method_nodes:
            # Skip if inside a class (already captured)
            parent = node.parent
            while parent:
                if parent.type == "class_declaration":
                    break
                parent = parent.parent
            else:  # Only add if not inside a class
                method_name = self._get_node_text(node.child_by_field_name("name"), source_code)
                parameters = self._extract_parameters(node, source_code)
                result["functions"].append({
                    "name": method_name,
                    "parameters": parameters,
                    "line": node.start_point[0] + 1
                })
        
        # Find imports
        import_nodes = []
        self._find_nodes_of_type(root_node, "import_declaration", import_nodes)
        
        for node in import_nodes:
            import_text = self._get_node_text(node, source_code)
            result["imports"].append(import_text)
    
    def _find_nodes_of_type(self, node, node_type: str, result: List):
        """Recursively find all nodes of a specific type."""
        if node.type == node_type:
            result.append(node)
        
        for child in node.children:
            self._find_nodes_of_type(child, node_type, result)
    
    def _get_node_text(self, node, source_code: bytes) -> str:
        """Get the text content of a node."""
        if node is None:
            return ""
        return source_code[node.start_byte:node.end_byte].decode('utf-8')
    
    def _extract_parameters(self, node, source_code: bytes) -> List[Dict]:
        """Extract parameters from a function or method node."""
        parameters = []
        
        # Find parameters node
        parameters_node = None
        for child in node.children:
            if child.type == "parameters" or child.type == "formal_parameters":
                parameters_node = child
                break
        
        if parameters_node is None:
            return parameters
        
        # Extract individual parameters
        for child in parameters_node.children:
            if child.type == "parameter" or child.type == "formal_parameter":
                param_name = ""
                param_type = ""
                
                # Try to get parameter name and type
                for subchild in child.children:
                    if subchild.type == "identifier":
                        param_name = self._get_node_text(subchild, source_code)
                    elif subchild.type == "type_identifier" or subchild.type == "primitive_type":
                        param_type = self._get_node_text(subchild, source_code)
                
                parameters.append({
                    "name": param_name,
                    "type": param_type
                })
        
        return parameters