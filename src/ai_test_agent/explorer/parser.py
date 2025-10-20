import ast
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_java as tsjava

PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())
JAVA_LANGUAGE = Language(tsjava.language())

class CodeParser:
    """Parse code files to extract structure and information."""
    
    def __init__(self):
        self.python_fallback = False
        self.language_errors: Dict[str, Exception] = {}
        self.parsers = {}

        language_map = {
            '.py': PY_LANGUAGE,
            '.js': JS_LANGUAGE,
            '.jsx': JS_LANGUAGE,
            '.ts': JS_LANGUAGE,
            '.tsx': JS_LANGUAGE,
            '.java': JAVA_LANGUAGE,
        }

        for extension, language in language_map.items():
            try:
                self.parsers[extension] = self._create_parser(language)
            except (ValueError, OSError) as exc:
                self.parsers[extension] = None
                self.language_errors[extension] = exc
                if extension == '.py':
                    self.python_fallback = True
                    warnings.warn(
                        "Falling back to Python AST parsing because the bundled "
                        "tree-sitter language library is incompatible with the installed "
                        "tree-sitter bindings. Consider upgrading the 'tree-sitter' package "
                        "to a version that supports the bundled grammars.",
                        RuntimeWarning,
                    )
        self.language_config = {
            '.py': {
                "class_node": "class_definition",
                "function_node": "function_definition",
                "import_nodes": ["import_statement", "import_from_statement"],
                "method_node": "function_definition",
                "class_body_node": "block",
                "call_node": "call",
            },
            '.js': {
                "class_node": "class_declaration",
                "function_node": "function_declaration",
                "arrow_function_node": "arrow_function",
                "import_nodes": ["import_statement"],
                "method_node": "method_definition",
                "class_body_node": "class_body",
                "call_node": "call_expression",
            },
            '.java': {
                "class_node": "class_declaration",
                "method_node": "method_declaration",
                "import_nodes": ["import_declaration"],
                "class_body_node": "class_body",
                "call_node": "method_invocation",
            }
        }
    
    def parse_file(self, file_path: Union[str, Path]) -> Dict:
        """Parse a single file and extract its structure."""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return {"error": f"File not found: {file_path}"}
            
            extension = file_path.suffix.lower()
            if extension not in self.parsers:
                return {"error": f"Unsupported file type: {extension}"}
        
            parser = self.parsers[extension]
            if parser is None:
                if extension == '.py' and self.python_fallback:
                    return self._parse_python_with_ast(file_path)
                error = self.language_errors.get(extension)
                if error:
                    return {"error": f"Parser unavailable for {extension}: {error}"}
                return {"error": f"Parser not available for {extension}"}

            with open(file_path, 'rb') as f:
                source_code = f.read()
            
            tree = parser.parse(bytes(source_code))
            
            # Check for parsing errors
            if tree.root_node.has_error:
                # Find the first error node and report its location
                error_node = self._find_first_error_node(tree.root_node)
                if error_node:
                    line = error_node.start_point[0] + 1
                    column = error_node.start_point[1]
                    return {"error": f"Syntax error in {file_path} at line {line}, column {column}"}
                else:
                    return {"error": f"Syntax error in {file_path}"}

            result = {
                "file_path": str(file_path),
                "language": extension,
                "classes": [],
                "functions": [],
                "imports": [],
                "dependencies": []
            }
            
            # Extract info based on language config
            self._extract_info(tree, source_code, result, file_path)
            
            return result
        except FileNotFoundError:
            return {"error": f"File not found: {file_path}"}
        except Exception as e:
            return {"error": f"An unexpected error occurred while parsing {file_path}: {e}"}
    
    def _parse_python_with_ast(self, file_path: Path) -> Dict:
        """Fallback parser for Python files using the stdlib ast module."""
        try:
            source_text = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            source_text = file_path.read_text(encoding='latin-1')

        try:
            tree = ast.parse(source_text, filename=str(file_path))
        except SyntaxError as exc:
            return {"error": f"Syntax error in {file_path} at line {exc.lineno}, column {exc.offset or 0}"}

        result = {
            "file_path": str(file_path),
            "language": ".py",
            "classes": [],
            "functions": [],
            "imports": [],
            "dependencies": []
        }

        imports, dependencies = self._collect_python_imports(tree, file_path, source_text)
        result["imports"].extend(imports)
        result["dependencies"].extend(dependencies)

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_entry = self._build_class_from_ast(node, source_text, file_path)
                result["classes"].append(class_entry)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_entry = self._build_function_from_ast(node, source_text)
                result["functions"].append(func_entry)

        return result

    def _collect_python_imports(self, tree: ast.AST, file_path: Path, source_text: str) -> Tuple[List[str], List[str]]:
        """Gather import statements and attempt to resolve local dependencies."""
        imports: List[str] = []
        dependencies: List[str] = []
        current_dir = file_path.parent

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                import_text = ast.get_source_segment(source_text, node) or ""
                imports.append(import_text)
                for alias in node.names:
                    module_name = alias.name
                    resolved = self._resolve_python_import(module_name, current_dir)
                    if resolved:
                        dependencies.append(resolved)
            elif isinstance(node, ast.ImportFrom):
                import_text = ast.get_source_segment(source_text, node) or ""
                imports.append(import_text)
                prefix = "." * node.level
                module_name = prefix + (node.module or "")
                if module_name:
                    resolved = self._resolve_python_import(module_name, current_dir)
                    if resolved:
                        dependencies.append(resolved)

        # Remove duplicates while preserving order
        imports = list(dict.fromkeys(imports))
        dependencies = list(dict.fromkeys(dep for dep in dependencies if dep))
        return imports, dependencies

    def _build_class_from_ast(self, node: ast.ClassDef, source_text: str, file_path: Path) -> Dict:
        """Construct a class entry from an AST node."""
        base_classes = [self._safe_unparse(base) for base in node.bases if base is not None]
        methods = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_entry = self._build_function_from_ast(child, source_text)
                methods.append(method_entry)

        return {
            "name": node.name,
            "base_classes": base_classes,
            "methods": methods,
            "line": node.lineno,
        }

    def _build_function_from_ast(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], source_text: str) -> Dict:
        """Construct a function/method entry from an AST node."""
        parameters = self._extract_python_parameters(node.args)
        calls = [self._safe_unparse(call.func) for call in ast.walk(node) if isinstance(call, ast.Call)]
        calls = [call for call in calls if call]

        return {
            "name": node.name,
            "parameters": parameters,
            "calls": calls,
            "line": node.lineno,
        }

    def _extract_python_parameters(self, args: ast.arguments) -> List[Dict]:
        """Extract parameter information from an ast.arguments node."""
        parameters: List[Dict] = []

        def add_param(arg: Optional[ast.arg], default: Optional[ast.expr] = None, prefix: str = ""):
            if arg is None:
                return
            name = prefix + arg.arg
            annotation = self._safe_unparse(arg.annotation)
            default_value = self._safe_unparse(default)
            parameters.append({
                "name": name,
                "type": annotation,
                "default": default_value
            })

        positional = list(args.posonlyargs) + list(args.args)
        positional_defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
        for arg, default in zip(positional, positional_defaults):
            add_param(arg, default)

        for kwarg, default in zip(args.kwonlyargs, args.kw_defaults):
            add_param(kwarg, default)

        add_param(args.vararg, prefix="*")
        add_param(args.kwarg, prefix="**")

        return parameters

    def _safe_unparse(self, node: Optional[ast.AST]) -> str:
        """Safely convert an AST node back to source."""
        if node is None:
            return ""
        try:
            return ast.unparse(node)
        except AttributeError:
            # ast.unparse introduced in Python 3.9; fall back to repr if unavailable
            return repr(node)

    def _extract_info(self, tree, source_code: bytes, result: Dict, file_path: Path):
        """Extract information from code using a language configuration."""
        extension = result["language"]
        config = self.language_config.get(extension)
        if not config:
            return

        root_node = tree.root_node

        # Extract classes and methods
        class_nodes = []
        self._find_nodes_of_type(root_node, config["class_node"], class_nodes)

        for node in class_nodes:
            class_name = self._get_node_text(node.child_by_field_name("name"), source_code)
            base_classes = self._extract_base_classes(node, source_code, config)
            methods = []
            
            class_body_node = None
            for child in node.children:
                if child.type == config["class_body_node"]:
                    class_body_node = child
                    break
            
            if class_body_node:
                method_nodes = []
                self._find_nodes_of_type(class_body_node, config["method_node"], method_nodes)
                
                for method_node in method_nodes:
                    method_name = self._get_node_text(method_node.child_by_field_name("name"), source_code)
                    parameters = self._extract_parameters(method_node, source_code)
                    function_calls = self._extract_function_calls(method_node, source_code, config)
                    methods.append({
                        "name": method_name,
                        "parameters": parameters,
                        "calls": function_calls,
                        "line": method_node.start_point[0] + 1
                    })
            
            result["classes"].append({
                "name": class_name,
                "base_classes": base_classes,
                "methods": methods,
                "line": node.start_point[0] + 1
            })

        # Extract functions defined outside of classes
        if config.get("function_node"):
            function_nodes = []
            self._find_nodes_of_type(root_node, config["function_node"], function_nodes)

            for func_node in function_nodes:
                parent = func_node.parent
                is_method = False
                while parent:
                    if parent.type == config["class_node"]:
                        is_method = True
                        break
                    parent = parent.parent

                if not is_method:
                    function_name = self._get_node_text(func_node.child_by_field_name("name"), source_code)
                    parameters = self._extract_parameters(func_node, source_code)
                    function_calls = self._extract_function_calls(func_node, source_code, config)
                    result["functions"].append({
                        "name": function_name,
                        "parameters": parameters,
                        "calls": function_calls,
                        "line": func_node.start_point[0] + 1
                    })

        # Extract imports and dependencies
        if extension == '.py':
            self._extract_python_dependencies(root_node, source_code, result, file_path)
        else:
            import_nodes = []
            for import_node_type in config.get("import_nodes", []):
                self._find_nodes_of_type(root_node, import_node_type, import_nodes)

            for node in import_nodes:
                import_text = self._get_node_text(node, source_code)
                result["imports"].append(import_text)

    def _extract_base_classes(self, node, source_code: bytes, config: Dict) -> List[str]:
        """Extract base classes from a class node."""
        base_classes = []
        if config.get("class_node") == "class_definition": # Python
            superclasses_node = node.child_by_field_name("superclasses")
            if superclasses_node:
                for child in superclasses_node.children:
                    if child.type == "identifier":
                        base_classes.append(self._get_node_text(child, source_code))
        elif config.get("class_node") == "class_declaration": # JS/Java
            heritage_node = None
            for child in node.children:
                if child.type == "class_heritage": # JS
                    heritage_node = child
                    break
                elif child.type == "superclass": # Java
                    heritage_node = child
                    break
            if heritage_node:
                for child in heritage_node.children:
                    if child.type == "identifier" or child.type == "type_identifier":
                        base_classes.append(self._get_node_text(child, source_code))
        return base_classes

    def _create_parser(self, language: Language) -> Parser:
        parser = Parser(language=language)
        return parser

    def _extract_function_calls(self, node, source_code: bytes, config: Dict) -> List[str]:
        """Extract function calls from a node."""
        calls = []
        call_nodes = []
        self._find_nodes_of_type(node, config["call_node"], call_nodes)
        
        for call_node in call_nodes:
            if config["call_node"] == "call": # Python
                function_name = self._get_node_text(call_node.child_by_field_name("function"), source_code)
                if function_name:
                    calls.append(function_name)
            elif config["call_node"] == "call_expression": # JavaScript
                function_name = self._get_node_text(call_node.child_by_field_name("function"), source_code)
                if function_name:
                    calls.append(function_name)
            elif config["call_node"] == "method_invocation": # Java
                function_name = self._get_node_text(call_node.child_by_field_name("name"), source_code)
                if function_name:
                    calls.append(function_name)
        
        return calls
    

    
    def _extract_python_dependencies(self, root_node, source_code: bytes, result: Dict, file_path: Path):
        """Extract and resolve Python dependencies."""
        import_nodes = []
        self._find_nodes_of_type(root_node, "import_statement", import_nodes)
        self._find_nodes_of_type(root_node, "import_from_statement", import_nodes)
        
        for node in import_nodes:
            import_text = self._get_node_text(node, source_code)
            result["imports"].append(import_text)
            
            if node.type == "import_statement":
                module_node = node.child_by_field_name("name")
                if module_node:
                    module_name = self._get_node_text(module_node, source_code)
                    resolved_path = self._resolve_python_import(module_name, file_path.parent)
                    if resolved_path:
                        result["dependencies"].append(resolved_path)
            
            elif node.type == "import_from_statement":
                module_node = node.child_by_field_name("module_name")
                if module_node:
                    module_name = self._get_node_text(module_node, source_code)
                    resolved_path = self._resolve_python_import(module_name, file_path.parent)
                    if resolved_path:
                        result["dependencies"].append(resolved_path)

    def _resolve_python_import(self, module_name: str, current_dir: Path) -> str:
        """Resolve a Python import to a file path."""
        # Handle relative imports
        if module_name.startswith('.'):
            parts = module_name.split('.')
            level = 0
            for part in parts:
                if part == '':
                    level += 1
                else:
                    break
            
            base_path = current_dir
            for _ in range(level - 1):
                base_path = base_path.parent
            
            module_path = base_path / Path(*parts[level:])
            
            if module_path.is_dir() and (module_path / "__init__.py").exists():
                return str(module_path / "__init__.py")
            elif (module_path.with_suffix(".py")).exists():
                return str(module_path.with_suffix(".py"))
        
        # For now, we don't handle absolute imports of project files
        # or installed packages. This will be improved later.
        return ""


    

    
    def _find_first_error_node(self, node):
        """Recursively find the first node that has an error."""
        if node.has_error:
            # If the node itself is an error or contains an error, we need to find the smallest node with the error
            for child in node.children:
                if child.has_error:
                    return self._find_first_error_node(child)
            return node # This node is the smallest one with the error
        return None

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
        parameters_node = node.child_by_field_name("parameters")

        if parameters_node:
            for param_node in parameters_node.children:
                param_name = ""
                param_type = ""
                default_value = ""

                if param_node.type == "identifier":
                    param_name = self._get_node_text(param_node, source_code)
                
                elif param_node.type == "typed_parameter":
                    param_name = self._get_node_text(param_node.child_by_field_name("name"), source_code)
                    param_type = self._get_node_text(param_node.child_by_field_name("type"), source_code)

                elif param_node.type == "default_parameter":
                    param_name = self._get_node_text(param_node.child_by_field_name("name"), source_code)
                    default_value = self._get_node_text(param_node.child_by_field_name("value"), source_code)

                elif param_node.type == "typed_default_parameter":
                    param_name = self._get_node_text(param_node.child_by_field_name("name"), source_code)
                    param_type = self._get_node_text(param_node.child_by_field_name("type"), source_code)
                    default_value = self._get_node_text(param_node.child_by_field_name("value"), source_code)

                if param_name:
                    parameters.append({
                        "name": param_name,
                        "type": param_type,
                        "default": default_value
                    })
        
        return parameters
