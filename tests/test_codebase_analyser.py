"""
test_analyzer.py - Unit tests for the Python code analyzer
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, mock_open
import yaml

from evaluator.codebase_analyser import PythonAnalyser, CodebaseMetrics


class TestCodebaseMetrics(unittest.TestCase):
    """Test the CodebaseMetrics dataclass"""
    
    def test_metrics_initialization(self):
        """Test metrics are initialized with default values"""
        metrics = CodebaseMetrics()
        self.assertEqual(metrics.file_count, 0)
        self.assertEqual(metrics.line_count, 0)
        self.assertEqual(metrics.class_count, 0)
        self.assertEqual(metrics.function_count, 0)
        self.assertEqual(len(metrics.imports), 0)
        self.assertEqual(len(metrics.frameworks), 0)
    
    def test_metrics_to_dict(self):
        """Test conversion to dictionary"""
        metrics = CodebaseMetrics(
            file_count=5,
            line_count=100,
            class_count=3,
            function_count=10
        )
        metrics.imports.add('os')
        metrics.imports.add('sys')
        metrics.frameworks.append('FastAPI')
        
        result = metrics.to_dict()
        
        self.assertEqual(result['files'], 5)
        self.assertEqual(result['lines'], 100)
        self.assertEqual(result['classes'], 3)
        self.assertEqual(result['functions'], 10)
        self.assertIn('os', result['imports'])
        self.assertIn('FastAPI', result['frameworks'])


class TestPythonAnalyzer(unittest.TestCase):
    """Test the PythonAnalyzer class"""
    
    def setUp(self):
        """Create a temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create mock config
        self.mock_config = {
            'analysis': {
                'skip_directories': ['venv', '__pycache__', '.git'],
                'entry_point_patterns': ['main.py', 'app.py'],
                'sample_priority_files': ['main.py', 'models.py'],
                'max_preview_lines': 50,
                'max_code_samples': 3
            },
            'frameworks': {
                'web': {'fastapi': 'FastAPI', 'flask': 'Flask'},
                'database': {'sqlalchemy': 'SQLAlchemy'}
            }
        }
        
        # Write config to temp file
        self.config_path = self.test_path / 'test_config.yaml'
        with open(self.config_path, 'w') as f:
            yaml.dump(self.mock_config, f)
    
    def tearDown(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.test_dir)
    
    def test_analyzer_initialization(self):
        """Test analyzer initializes with config"""
        analyser = PythonAnalyser(str(self.config_path))
        
        self.assertIn('fastapi', analyser.frameworks)
        self.assertEqual(analyser.frameworks['fastapi'], 'FastAPI')
    
    def test_should_skip(self):
        """Test directory skipping logic"""
        analyser = PythonAnalyser(str(self.config_path))

        # Should skip venv
        venv_path = self.test_path / 'venv' / 'lib' / 'file.py'
        self.assertTrue(analyser._should_skip(venv_path))

        # Should not skip regular path
        regular_path = self.test_path / 'src' / 'file.py'
        self.assertFalse(analyser._should_skip(regular_path))

    def test_analyze_file(self):
        """Test analyzing a single Python file"""
        analyser = PythonAnalyser(str(self.config_path))

        # Create a test Python file
        test_file = self.test_path / 'test.py'
        test_content = '''
import os
import sys
from typing import List

class TestClass:
    def method1(self):
        pass
    
    def method2(self):
        pass

def function1():
    pass

def function2():
    return 42
'''
        test_file.write_text(test_content)
        
        # Analyze the file
        result = analyser._analyse_file(test_file)
        
        self.assertEqual(result['classes'], 1)
        self.assertEqual(result['functions'], 4)
        self.assertGreater(result['lines'], 10)
        self.assertIn('os', result['imports'])
        self.assertIn('sys', result['imports'])
    
    def test_analyze_structure(self):
        """Test analyzing directory structure"""
        analyzer = PythonAnalyser(str(self.config_path))
        
        # Create test structure
        (self.test_path / 'src').mkdir()
        (self.test_path / 'src' / '__init__.py').touch()
        (self.test_path / 'tests').mkdir()
        (self.test_path / 'main.py').touch()
        (self.test_path / 'app.py').touch()
        
        # Analyze structure
        structure = analyzer._analyse_structure(self.test_path)
        
        self.assertTrue(structure['has_tests'])
        self.assertIn('main.py', structure['entry_points'])
        self.assertIn('app.py', structure['entry_points'])
        self.assertIn('src', structure['packages'])
    
    def test_get_code_samples(self):
        """Test extracting code samples"""
        analyzer = PythonAnalyser(str(self.config_path))
        
        # Create test files
        main_file = self.test_path / 'main.py'
        main_content = 'from fastapi import FastAPI\napp = FastAPI()\n'
        main_file.write_text(main_content)
        
        models_file = self.test_path / 'models.py'
        models_content = 'class User:\n    pass\n'
        models_file.write_text(models_content)
        
        # Get samples
        samples = analyzer._get_code_samples(self.test_path, max_samples=2)
        
        self.assertLessEqual(len(samples), 2)
        if samples:
            self.assertIn('file', samples[0])
            self.assertIn('preview', samples[0])
            # Check priority files are selected first
            file_names = [s['file'] for s in samples]
            self.assertIn('main.py', file_names)
    
    def test_analyze_codebase_integration(self):
        """Test full codebase analysis"""
        analyzer = PythonAnalyser(str(self.config_path))
        
        # Create a mini codebase
        (self.test_path / 'src').mkdir()
        (self.test_path / 'src' / '__init__.py').touch()
        
        main_file = self.test_path / 'main.py'
        main_content = '''
from fastapi import FastAPI
import sqlalchemy

app = FastAPI()

class User:
    pass

def get_user():
    return User()
'''
        main_file.write_text(main_content)
        
        # Analyze the codebase
        result = analyzer.analyse_codebase(str(self.test_path))
        
        self.assertIn('metrics', result)
        self.assertIn('structure', result)
        self.assertIn('samples', result)
        
        # Check metrics
        metrics = result['metrics']
        self.assertEqual(metrics['files'], 2)  
        self.assertEqual(metrics['classes'], 1)
        self.assertEqual(metrics['functions'], 1)
        self.assertIn('FastAPI', metrics['frameworks'])
        self.assertIn('SQLAlchemy', metrics['frameworks'])
        
        # Check structure
        structure = result['structure']
        self.assertIn('main.py', structure['entry_points'])
        self.assertIn('src', structure['packages'])
    
    def test_nonexistent_path(self):
        """Test handling of non-existent path"""
        analyzer = PythonAnalyser(str(self.config_path))
        
        with self.assertRaises(ValueError) as context:
            analyzer.analyse_codebase('/nonexistent/path')
        
        self.assertIn('does not exist', str(context.exception))
    
    def test_empty_codebase(self):
        """Test analyzing empty codebase"""
        analyzer = PythonAnalyser(str(self.config_path))
        
        # Create empty directory
        empty_dir = self.test_path / 'empty'
        empty_dir.mkdir()
        
        result = analyzer.analyse_codebase(str(empty_dir))
        
        self.assertEqual(result['metrics']['files'], 0)
        self.assertEqual(result['metrics']['lines'], 0)
        self.assertEqual(len(result['samples']), 0)
    
    def test_framework_detection(self):
        """Test framework detection from imports"""
        analyzer = PythonAnalyser(str(self.config_path))
        
        # Create file with framework imports
        test_file = self.test_path / 'app.py'
        test_content = '''
import fastapi
from flask import Flask
import sqlalchemy as sa
'''
        test_file.write_text(test_content)
        
        result = analyzer.analyse_codebase(str(self.test_path))
        
        frameworks = result['metrics']['frameworks']
        self.assertIn('FastAPI', frameworks)
        self.assertIn('Flask', frameworks)
        self.assertIn('SQLAlchemy', frameworks)


class TestAnalyzerErrorHandling(unittest.TestCase):
    """Test error handling in analyzer"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create minimal config
        self.config_path = self.test_path / 'config.yaml'
        config = {
            'analysis': {
                'skip_directories': [],
                'entry_point_patterns': [],
                'sample_priority_files': [],
                'max_preview_lines': 50,
                'max_code_samples': 3
            },
            'frameworks': {}
        }
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_invalid_python_file(self):
        """Test handling of files with syntax errors"""
        analyzer = PythonAnalyser(str(self.config_path))
        
        # Create file with invalid Python
        bad_file = self.test_path / 'bad.py'
        bad_file.write_text('def function(\n    pass')  # Invalid syntax
        
        # Should not crash
        result = analyzer._analyse_file(bad_file)
        self.assertIsNotNone(result)
        self.assertGreater(result['lines'], 0)  # Should at least count lines
    
    def test_file_read_permission(self):
        """Test handling of permission errors"""
        analyzer = PythonAnalyser(str(self.config_path))
        
        # This test is platform-specific and might need adjustment
        # For now, just ensure the analyzer doesn't crash on exceptions
        result = analyzer.analyse_codebase(str(self.test_path))
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()