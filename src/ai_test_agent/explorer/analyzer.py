import os
import fnmatch
import warnings
import networkx as nx
from pathlib import Path
from typing import Dict, Optional, List
from .parser import CodeParser

class ProjectAnalyzer:
    """Analyze project structure and dependencies."""
    
    def __init__(self, project_path: str, parser: Optional[CodeParser] = None, include: Optional[List[str]] = None, exclude: Optional[List[str]] = None):
        self.project_path = Path(project_path)
        self.parser = parser or CodeParser()
        default_excludes = [
            ".venv/**",
            "node_modules/**",
            "build/**",
            "dist/**",
            "__pycache__/**",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            "*.class",
        ]
        self.include = include or ["**/*"]
        self.exclude = (exclude or []) + default_excludes
        self.dependency_graph = nx.DiGraph()
        self.call_graph = nx.DiGraph()
        self.file_info = {}
        self.business_logic = {}
    
    def analyze_project(self) -> Dict:
        """Analyze the entire project structure."""
        print(f"Analyzing project at: {self.project_path}")
        if not self.project_path.exists():
            raise ValueError(f"Project path does not exist: {self.project_path}")
        
        # Parse all code files
        self._parse_all_files()
        
        # Build dependency graph and call graph
        self._build_dependency_graph()
        
        # Extract business logic
        self._extract_business_logic()
        
        return {
            "project_path": str(self.project_path),
            "files": self.file_info,
            "dependency_graph": self._serialize_graph(self.dependency_graph),
            "call_graph": self._serialize_graph(self.call_graph),
            "business_logic": self.business_logic,
            "summary": self._generate_summary()
        }
    
    def _parse_all_files(self):
        """Parse all code files in the project that match the include/exclude patterns."""
        for root, dirs, files in os.walk(self.project_path):
            # Remove excluded directories from traversal
            dirs[:] = [
                d for d in dirs
                if not any(
                    fnmatch.fnmatch(str(Path(root, d).relative_to(self.project_path)), pattern.rstrip("/**"))
                    for pattern in self.exclude
                    if pattern.endswith("/**")
                )
            ]

            for file in files:
                file_path = Path(root) / file
                # Check if the file should be included
                if not any(fnmatch.fnmatch(str(file_path.relative_to(self.project_path)), pattern) for pattern in self.include):
                    continue
                # Check if the file should be excluded
                if any(fnmatch.fnmatch(str(file_path.relative_to(self.project_path)), pattern) for pattern in self.exclude):
                    continue

                if file_path.suffix.lower() in self.parser.parsers:
                    try:
                        file_info = self.parser.parse_file(file_path)
                        self.file_info[str(file_path)] = file_info
                    except Exception as e:
                        print(f"Error parsing {file_path}: {e}")
    
    def _build_dependency_graph(self):
        """Build a dependency graph and a call graph from the parsed files."""
        for file_path, info in self.file_info.items():
            # Add file as a node
            self.dependency_graph.add_node(file_path, **info)
            
            # Process imports to add edges
            for resolved_path in info.get("dependencies", []):
                if resolved_path in self.file_info:
                    self.dependency_graph.add_edge(file_path, resolved_path, type="imports")

            # Process inheritance to add edges
            for cls in info.get("classes", []):
                for base_class in cls.get("base_classes", []):
                    # This is a simplified resolution. A real implementation would need to resolve the base class to a specific file.
                    self.dependency_graph.add_edge(file_path, base_class, type="inherits")

            # Build call graph
            for func in info.get("functions", []):
                func_name = func["name"]
                self.call_graph.add_node(f"{file_path}::{func_name}")
                for call in func.get("calls", []):
                    # This is a simplified resolution. A real implementation would need to resolve the call to a specific function in a specific file.
                    self.call_graph.add_edge(f"{file_path}::{func_name}", call)

            for cls in info.get("classes", []):
                cls_name = cls["name"]
                for method in cls.get("methods", []):
                    method_name = method["name"]
                    self.call_graph.add_node(f"{file_path}::{cls_name}::{method_name}")
                    for call in method.get("calls", []):
                        # This is a simplified resolution. A real implementation would need to resolve the call to a specific function in a specific file.
                        self.call_graph.add_edge(f"{file_path}::{cls_name}::{method_name}", call)

    def _extract_business_logic(self):
        """Extract business logic from the parsed files."""
        scores = self._analyze_call_graph()
        
        for file_path, info in self.file_info.items():
            business_functions = []
            
            # Analyze functions for business logic indicators
            for func in info.get("functions", []):
                score = self._is_business_function(func) + scores.get(f"{file_path}::{func['name']}", 0)
                if score > 0.5: # Threshold can be adjusted
                    func["business_score"] = score
                    business_functions.append(func)
            
            # Analyze class methods for business logic indicators
            for cls in info.get("classes", []):
                business_methods = []
                for method in cls.get("methods", []):
                    score = self._is_business_function(method) + scores.get(f"{file_path}::{cls['name']}::{method['name']}", 0)
                    if score > 0.5: # Threshold can be adjusted
                        method["business_score"] = score
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

    def _is_business_function(self, func: Dict) -> float:
        """Determine if a function is likely business logic and return a score."""
        name = func.get("name", "").lower()
        score = 0.0

        # Negative keywords
        skip_patterns = [
            "test_", "_test", "setup", "teardown", "mock", "stub",
            "__init__", "__str__", "__repr__", "helper", "util"
        ]
        if any(pattern in name for pattern in skip_patterns):
            return 0.0

        # Positive keywords
        business_keywords = {
            "create": 0.5, "update": 0.5, "delete": 0.5, "process": 0.7, "calculate": 0.8, "validate": 0.6,
            "transform": 0.7, "generate": 0.6, "execute": 0.7, "perform": 0.7, "handle": 0.6, "manage": 0.6,
            "service": 0.8, "controller": 0.8, "repository": 0.7, "dao": 0.7, "entity": 0.5, "model": 0.5
        }
        for keyword, weight in business_keywords.items():
            if keyword in name:
                score += weight

        # Bonus for having parameters
        if func.get("parameters"): 
            score += 0.1

        return score

    def _analyze_call_graph(self) -> Dict[str, float]:
        """Analyze the call graph to identify important functions."""
        if not self.call_graph:
            return {}

        # Calculate PageRank to find important nodes
        try:
            pagerank = nx.pagerank(self.call_graph)
        except nx.PowerIterationFailedConvergence:
            pagerank = {node: 1.0 / len(self.call_graph) for node in self.call_graph.nodes}
        except (ImportError, ModuleNotFoundError) as exc:
            if "scipy" in str(exc).lower():
                warnings.warn(
                    "SciPy is not installed; falling back to degree centrality "
                    "for call-graph scoring. Install 'scipy' to enable PageRank-based "
                    "prioritization.",
                    RuntimeWarning,
                )
                pagerank = nx.degree_centrality(self.call_graph)
            else:
                raise

        # Normalize scores
        max_rank = max(pagerank.values()) if pagerank else 1.0
        return {node: rank / max_rank for node, rank in pagerank.items()}

    def _serialize_graph(self, graph) -> Dict:
        """Serialize a graph for JSON output."""
        return {
            "nodes": [
                {
                    "id": node,
                    **graph.nodes[node]
                }
                for node in graph.nodes
            ],
            "edges": [
                {
                    "source": source,
                    "target": target
                }
                for source, target in graph.edges
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
