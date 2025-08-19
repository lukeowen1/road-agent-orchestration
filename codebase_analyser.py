"""
A script to analyse Python codebases and extracts metrics such as total files, classes etc.
"""
import ast
from pathlib import Path
from typing import Dict, List, Set
from dataclasses import dataclass, field


@dataclass
class CodebaseMetrics:
    """Simple metrics about a Python codebase"""
    file_count: int = 0
    line_count: int = 0
    class_count: int = 0
    function_count: int = 0
    imports: Set[str] = field(default_factory=set)
    frameworks: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "files": self.file_count,
            "lines": self.line_count,
            "classes": self.class_count,
            "functions": self.function_count,
            "imports": list(self.imports),
            "frameworks": self.frameworks
        }


class PythonAnalyzer:
    """Analyzes Python codebases"""
    
    # Common Python frameworks
    FRAMEWORKS = {
        'flask': 'Flask',
        'django': 'Django',
        'fastapi': 'FastAPI',
        'pandas': 'Pandas',
        'numpy': 'NumPy',
        'pytest': 'pytest',
        'sqlalchemy': 'SQLAlchemy',
    }
    
    def analyze_codebase(self, path: str) -> Dict:
        """
        Analyze a Python codebase and return metrics + structure
        
        Args:
            path: Path to the codebase directory
            
        Returns:
            Dictionary with metrics, structure, and code samples
        """
        base_path = Path(path)
        if not base_path.exists():
            raise ValueError(f"Path {path} does not exist")
        
        metrics = CodebaseMetrics()
        structure = self._analyze_structure(base_path)
        
        # Analyze all Python files
        for py_file in base_path.rglob('*.py'):
            if self._should_skip(py_file):
                continue
                
            metrics.file_count += 1
            file_metrics = self._analyze_file(py_file)
            
            metrics.line_count += file_metrics['lines']
            metrics.class_count += file_metrics['classes']
            metrics.function_count += file_metrics['functions']
            metrics.imports.update(file_metrics['imports'])
        
        # Detect frameworks from imports
        for imp in metrics.imports:
            for framework_key, framework_name in self.FRAMEWORKS.items():
                if framework_key in imp.lower():
                    if framework_name not in metrics.frameworks:
                        metrics.frameworks.append(framework_name)
        
        # Get code samples
        samples = self._get_code_samples(base_path, max_samples=3)
        
        return {
            "metrics": metrics.to_dict(),
            "structure": structure,
            "samples": samples
        }
    
    def _should_skip(self, file_path: Path) -> bool:
        """Check if we should skip this file/directory"""
        skip_dirs = {'venv', '.venv', '__pycache__', 'node_modules', '.git'}
        return any(part in skip_dirs for part in file_path.parts)
    
    def _analyze_file(self, file_path: Path) -> Dict:
        """Analyze a single Python file"""
        result = {
            'lines': 0,
            'classes': 0,
            'functions': 0,
            'imports': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                result['lines'] = len(content.splitlines())
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    result['classes'] += 1
                elif isinstance(node, ast.FunctionDef):
                    result['functions'] += 1
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        result['imports'].append(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        result['imports'].append(node.module.split('.')[0])
        except:
            # If AST parsing fails, at least count lines
            pass
        
        return result
    
    def _analyze_structure(self, base_path: Path) -> Dict:
        """Analyze the directory structure"""
        structure = {
            'has_tests': False,
            'has_docs': False,
            'entry_points': [],
            'packages': []
        }
        
        # Check for common directories
        if (base_path / 'tests').exists() or (base_path / 'test').exists():
            structure['has_tests'] = True
        
        if (base_path / 'docs').exists():
            structure['has_docs'] = True
        
        # Find entry points
        for pattern in ['main.py', 'app.py', '__main__.py', 'run.py']:
            for entry in base_path.rglob(pattern):
                if not self._should_skip(entry):
                    structure['entry_points'].append(str(entry.relative_to(base_path)))
        
        # Find packages (directories with __init__.py)
        for init_file in base_path.rglob('__init__.py'):
            if not self._should_skip(init_file):
                package = init_file.parent.relative_to(base_path)
                structure['packages'].append(str(package))
        
        return structure
    
    def _get_code_samples(self, base_path: Path, max_samples: int = 3) -> List[Dict]:
        """Get a few representative code samples"""
        samples = []
        priority_files = ['main.py', 'app.py', 'models.py', 'views.py']
        
        # Try to get priority files first
        for pattern in priority_files:
            if len(samples) >= max_samples:
                break
                
            for file_path in base_path.rglob(pattern):
                if self._should_skip(file_path):
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[:50]  # First 50 lines
                        samples.append({
                            'file': str(file_path.relative_to(base_path)),
                            'preview': ''.join(lines)
                        })
                        break
                except:
                    pass
                    
                if len(samples) >= max_samples:
                    break
        
        return samples