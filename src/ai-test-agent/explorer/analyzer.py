import os
import networkx as nx
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from .parser import CodeParser

class ProjectAnalyzer:
    """Analyze project structure and dependencies."""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.parser = CodeParser()
        self.dependency_graph = nx.DiGraph()
        self.file_info = {}
        self.business_logic = {}
    
    def analyze_project(self) -> Dict:
        """Analyze the entire project structure."""
        if not self.project_path.exists():
            raise ValueError(f"Project path does not exist: {self.project_path}")
        
        # Parse all code files
        self._parse_all_files()
        
        # Build dependency graph
        self._build_dependency_graph()
        
        # Extract business logic
        self._extract_business_logic()
        
        return {
            "project_path": str(self.project_path),
            "files": self.file_info,
            "dependency_graph": self._serialize_graph(),
            "business_logic": self.business_logic,
            "summary": self._generate_summary()
        }
    
    def _parse_all_files(self):
        """Parse all code files in the project."""
        supported_extensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.java']
        
        for root, _, files in os.walk(self.project_path):
            # Skip hidden directories and common build/cache directories
            if any(part.startswith('.') for part in Path(root).parts):
                continue
            if any(part in ['node_modules', '__pycache__', 'target', 'build', 'dist'] for part in Path(root).parts):
                continue
            
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in supported_extensions:
                    try:
                        file_info = self.parser.parse_file(file_path)
                        self.file_info[str(file_path)] = file_info
                    except Exception as e:
                        print(f"Error parsing {file_path}: {e}")
    
    def _build_dependency_graph(self):
        """Build a dependency graph from the parsed files."""
        for file_path, info in self.file_info.items():
            # Add file as a node
            self.dependency_graph.add_node(file_path, **info)
            
            # Process imports to add edges
            for import_stmt in info.get("imports", []):
                # Try to resolve import to a file path
                resolved_path = self._resolve_import(file_path, import_stmt)
                if resolved_path and resolved_path in self.file_info:
                    self.dependency_graph.add_edge(file_path, resolved_path)
    
    def _resolve_import(self, file_path: str, import_stmt: str) -> Optional[str]:
        """Resolve an import statement to a file path."""
        file_dir = Path(file_path).parent
        extension = Path(file_path).suffix.lower()
        
        # Simple resolution for demonstration
        # In a real implementation, this would be more sophisticated
        
        if extension == '.py':
            # Handle Python imports
            if import_stmt.startswith("from "):
                import_path = import_stmt.split(" ")[1].split(" import")[0]
            else:
                import_path = import_stmt.split("import ")[1].split(" as")[0].strip()
            
            # Convert dot notation to path
            parts = import_path.split(".")
            
            # Try relative imports first
            if parts[0] == "":
                # Relative import
                resolved_path = file_dir
                for part in parts[1:]:
                    if part == "":
                        continue
                    resolved_path = resolved_path / part
                resolved_path = resolved_path.with_suffix(".py")
            else:
                # Absolute import
                # Try to find the module in the project
                for root, _, files in os.walk(self.project_path):
                    if any(part.startswith('.') for part in Path(root).parts):
                        continue
                    
                    if Path(root).name == parts[0]:
                        resolved_path = Path(root)
                        for part in parts[1:]:
                            resolved_path = resolved_path / part
                        resolved_path = resolved_path.with_suffix(".py")
                        break
                else:
                    # Not found in project
                    return None
            
            if resolved_path.exists():
                return str(resolved_path)
            
            # Try as a package (directory with __init__.py)
            if extension == '.py':
                package_path = resolved_path.with_name(resolved_path.name + "/__init__.py")
                if package_path.exists():
                    return str(package_path)
        
        elif extension in ['.js', '.jsx', '.ts', '.tsx']:
            # Handle JavaScript/TypeScript imports
            if import_stmt.startswith("import "):
                import_path = import_stmt.split("from ")[1].strip().strip("'\"")
            else:
                import_path = import_stmt.strip().strip("'\"")
            
            # Handle relative imports
            if import_path.startswith("./") or import_path.startswith("../"):
                resolved_path = (file_dir / import_path).resolve()
                
                # Try different extensions
                for ext in ['.js', '.jsx', '.ts', '.tsx', '.json']:
                    test_path = Path(str(resolved_path) + ext)
                    if test_path.exists():
                        return str(test_path)
                
                # Try as directory with index file
                for ext in ['.js', '.jsx', '.ts', '.tsx']:
                    test_path = resolved_path / f"index{ext}"
                    if test_path.exists():
                        return str(test_path)
            else:
                # Node module or absolute import
                # For simplicity, we'll skip these in this example
                return None
        
        elif extension == '.java':
            # Handle Java imports
            if import_stmt.startswith("import "):
                import_path = import_stmt.split(" ")[1].strip().strip(";")
                
                # Convert package notation to path
                parts = import_path.split(".")
                
                # Try to find the class in the project
                for root, _, files in os.walk(self.project_path):
                    if any(part.startswith('.') for part in Path(root).parts):
                        continue
                    
                    for file in files:
                        if file.endswith(".java"):
                            file_path = Path(root) / file
                            try:
                                file_info = self.parser.parse_file(file_path)
                                for cls in file_info.get("classes", []):
                                    if cls["name"] == parts[-1]:
                                        return str(file_path)
                            except:
                                continue
        
        return None
    
    def _extract_business_logic(self):
        """Extract business logic from the parsed files."""
        for file_path, info in self.file_info.items():
            business_functions = []
            
            # Analyze functions for business logic indicators
            for func in info.get("functions", []):
                if self._is_business_function(func):
                    business_functions.append(func)
            
            # Analyze class methods for business logic indicators
            for cls in info.get("classes", []):
                business_methods = []
                for method in cls.get("methods", []):
                    if self._is_business_function(method):
                        business_methods.append(method)
                
                if business_methods:
                    self.business_logic[file_path] = {
                        "type": "class",
                        "name": cls["name"],
                        "business_methods": business_methods
                    }
            
            if business_functions:
                self.business_logic[file_path] = {
                    "type": "functions",
                    "functions": business_functions
                }
    
    def _is_business_function(self, func: Dict) -> bool:
        """Determine if a function is likely business logic."""
        # This is a simplified heuristic
        # In a real implementation, this would use NLP and more sophisticated analysis
        
        name = func.get("name", "").lower()
        
        # Skip common utility/test functions
        skip_patterns = [
            "test_", "_test", "setup", "teardown", "mock", "stub",
            "__init__", "__str__", "__repr__", "helper", "util"
        ]
        
        if any(pattern in name for pattern in skip_patterns):
            return False
        
        # Look for business-related keywords
        business_keywords = [
            "create", "update", "delete", "process", "calculate", "validate",
            "transform", "generate", "execute", "perform", "handle", "manage"
        ]
        
        return any(keyword in name for keyword in business_keywords)
    
    def _serialize_graph(self) -> Dict:
        """Serialize the dependency graph for JSON output."""
        return {
            "nodes": [
                {
                    "id": node,
                    **self.dependency_graph.nodes[node]
                }
                for node in self.dependency_graph.nodes
            ],
            "edges": [
                {
                    "source": source,
                    "target": target
                }
                for source, target in self.dependency_graph.edges
            ]
        }
    
    def _generate_summary(self) -> Dict:
        """Generate a summary of the project analysis."""
        total_files = len(self.file_info)
        total_classes = sum(len(info.get("classes", [])) for info in self.file_info.values())
        total_functions = sum(len(info.get("functions", [])) for info in self.file_info.values())
        
        language_counts = {}
        for info in self.file_info.values():
            lang = info.get("language", "unknown")
            language_counts[lang] = language_counts.get(lang, 0) + 1
        
        return {
            "total_files": total_files,
            "total_classes": total_classes,
            "total_functions": total_functions,
            "languages": language_counts,
            "business_logic_files": len(self.business_logic)
        }