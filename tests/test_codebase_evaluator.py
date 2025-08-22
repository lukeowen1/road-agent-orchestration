"""
test_evaluator.py - Unit tests for the complexity evaluator
"""
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import yaml

from evaluator.codebase_evaluator import ComplexityEvaluator


class TestComplexityEvaluator(unittest.TestCase):
    """Test the ComplexityEvaluator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create mock config
        self.mock_config = {
            'llm': {
                'model': 'gpt-3.5-turbo',
                'temperature': 0.1,
                'max_tokens': 1000
            },
            'complexity': {
                'simple': {'max_files': 50, 'max_lines': 5000},
                'moderate': {'max_files': 150, 'max_lines': 20000}
            },
            'prompts': {
                'system_message': 'You are an evaluator. Simple: < {simple_max_files} files',
                'evaluation_template': 'Files: {files}, Lines: {lines}, Frameworks: {frameworks}, Entry points: {entry_points}'
            }
        }
        
        # Write config
        self.config_path = self.test_path / 'config.yaml'
        with open(self.config_path, 'w') as f:
            yaml.dump(self.mock_config, f)
        
        # Sample analysis data
        self.sample_analysis = {
            'metrics': {
                'files': 10,
                'lines': 500,
                'classes': 5,
                'functions': 20,
                'frameworks': ['FastAPI', 'SQLAlchemy']
            },
            'structure': {
                'has_tests': True,
                'entry_points': ['main.py'],
                'packages': ['src', 'tests']
            },
            'samples': [
                {
                    'file': 'main.py',
                    'preview': 'from fastapi import FastAPI\napp = FastAPI()'
                }
            ]
        }
    
    def tearDown(self):
        """Clean up"""
        import shutil
        shutil.rmtree(self.test_dir)

    @patch('evaluator.codebase_evaluator.ChatOpenAI')
    def test_evaluator_initialization(self, mock_chat):
        """Test evaluator initialization with config"""
        evaluator = ComplexityEvaluator(config_path=str(self.config_path))
        
        # Should create LLM with config settings
        mock_chat.assert_called_once_with(
            model='gpt-3.5-turbo',
            temperature=0.1,
            max_tokens=1000
        )
    
    def test_evaluator_with_provided_llm(self):
        """Test evaluator with pre-configured LLM"""
        mock_llm = Mock()
        evaluator = ComplexityEvaluator(
            llm=mock_llm,
            config_path=str(self.config_path)
        )
        
        self.assertEqual(evaluator.llm, mock_llm)
    
    def test_create_prompt(self):
        """Test prompt creation"""
        evaluator = ComplexityEvaluator(
            llm=Mock(),
            config_path=str(self.config_path)
        )
        
        messages = evaluator._create_prompt(self.sample_analysis)
        
        self.assertEqual(len(messages), 2)
        
        # Check system message
        system_msg = messages[0].content
        self.assertIn('evaluator', system_msg.lower())
        
        # Check human message contains analysis data
        human_msg = messages[1].content
        self.assertIn('10', human_msg)  # files
        self.assertIn('500', human_msg)  # lines
        self.assertIn('FastAPI', human_msg)
        self.assertIn('SQLAlchemy', human_msg)
    
    @patch('evaluator.codebase_evaluator.ChatOpenAI')
    def test_evaluate_with_valid_json(self, mock_chat_class):
        """Test evaluation with valid JSON response"""
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = json.dumps({
            'complexity_level': 'simple',
            'complexity_score': 3.5,
            'can_use_llm': True,
            'reasoning': 'Small codebase with clear structure',
            'confidence': 0.9
        })
        
        mock_llm = Mock()
        mock_llm.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_llm
        
        evaluator = ComplexityEvaluator(config_path=str(self.config_path))
        result = evaluator.evaluate(self.sample_analysis)
        
        self.assertEqual(result['complexity_level'], 'simple')
        self.assertEqual(result['complexity_score'], 3.5)
        self.assertTrue(result['can_use_llm'])
        self.assertEqual(result['confidence'], 0.9)
    
    @patch('evaluator.codebase_evaluator.ChatOpenAI')
    def test_evaluate_with_invalid_json(self, mock_chat_class):
        """Test evaluation with invalid JSON response"""
        # Mock LLM response with invalid JSON
        mock_response = Mock()
        mock_response.content = "This is not valid JSON. The codebase is simple."
        
        mock_llm = Mock()
        mock_llm.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_llm
        
        evaluator = ComplexityEvaluator(config_path=str(self.config_path))
        result = evaluator.evaluate(self.sample_analysis)
        
        # Should use fallback
        self.assertIn('complexity_level', result)
        self.assertIn('can_use_llm', result)
        self.assertEqual(result['confidence'], 0.5)  # Fallback confidence
        self.assertIn('fallback', result['reasoning'].lower())
    
    def test_create_fallback_decision(self):
        """Test fallback decision creation"""
        evaluator = ComplexityEvaluator(
            llm=Mock(),
            config_path=str(self.config_path)
        )
        
        # Test simple detection
        simple_response = "This is a simple codebase, suitable for processing"
        result = evaluator._create_fallback_decision(simple_response)
        self.assertEqual(result['complexity_level'], 'simple')
        self.assertTrue(result['can_use_llm'])
        
        # Test complex detection
        complex_response = "This codebase is too complex"
        result = evaluator._create_fallback_decision(complex_response)
        self.assertEqual(result['complexity_level'], 'complex')
        
        # Test moderate detection (default)
        moderate_response = "This codebase has some challenges"
        result = evaluator._create_fallback_decision(moderate_response)
        self.assertEqual(result['complexity_level'], 'moderate')
    
    def test_prompt_template_formatting(self):
        """Test that prompt templates are properly formatted"""
        evaluator = ComplexityEvaluator(
            llm=Mock(),
            config_path=str(self.config_path)
        )
        
        # Analysis with no frameworks
        analysis_no_frameworks = {
            'metrics': {
                'files': 5,
                'lines': 100,
                'classes': 2,
                'functions': 10,
                'frameworks': []
            },
            'structure': {
                'has_tests': False,
                'entry_points': [],
                'packages': []
            },
            'samples': []
        }
        
        messages = evaluator._create_prompt(analysis_no_frameworks)
        human_msg = messages[1].content
        
        # Should handle empty lists gracefully
        self.assertIn('None detected', human_msg)  # for frameworks
        self.assertIn('None found', human_msg)  # for entry points
    
    @patch('evaluator.codebase_evaluator.ChatOpenAI')
    def test_evaluate_with_large_codebase(self, mock_chat_class):
        """Test evaluation with large codebase metrics"""
        large_analysis = {
            'metrics': {
                'files': 200,
                'lines': 50000,
                'classes': 100,
                'functions': 500,
                'frameworks': ['Django', 'Celery', 'Redis']
            },
            'structure': {
                'has_tests': True,
                'entry_points': ['manage.py'],
                'packages': ['app'] * 20  # Many packages
            },
            'samples': []
        }
        
        mock_response = Mock()
        mock_response.content = json.dumps({
            'complexity_level': 'complex',
            'complexity_score': 8.5,
            'can_use_llm': False,
            'reasoning': 'Too large for LLM context',
            'confidence': 0.95
        })
        
        mock_llm = Mock()
        mock_llm.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_llm
        
        evaluator = ComplexityEvaluator(config_path=str(self.config_path))
        result = evaluator.evaluate(large_analysis)
        
        self.assertEqual(result['complexity_level'], 'complex')
        self.assertFalse(result['can_use_llm'])
        self.assertGreater(result['complexity_score'], 7)


class TestEvaluatorIntegration(unittest.TestCase):
    """Integration tests for evaluator"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / 'config.yaml'
        
        config = {
            'llm': {
                'model': 'gpt-3.5-turbo',
                'temperature': 0.1,
                'max_tokens': 1000
            },
            'complexity': {
                'simple': {'max_files': 50},
                'moderate': {'max_files': 150}
            },
            'prompts': {
                'system_message': 'Evaluate complexity. Simple: < {simple_max_files} files, Moderate: < {moderate_max_files} files',
                'evaluation_template': 'Analysis: Files: {files}, Lines: {lines}, Frameworks: {frameworks}, Has tests: {has_tests}, Entry: {entry_points}, Packages: {packages}, Sample: {sample_file}: {code_preview}'
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)
    
    @patch('evaluator.codebase_evaluator.ChatOpenAI')
    def test_full_evaluation_flow(self, mock_chat_class):
        """Test complete evaluation flow"""
        # Setup mock LLM
        mock_response = Mock()
        mock_response.content = json.dumps({
            'complexity_level': 'moderate',
            'complexity_score': 5.5,
            'can_use_llm': True,
            'reasoning': 'Moderate complexity but manageable',
            'confidence': 0.8
        })
        
        mock_llm = Mock()
        mock_llm.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_llm
        
        # Create evaluator
        evaluator = ComplexityEvaluator(config_path=str(self.config_path))
        
        # Test analysis
        analysis = {
            'metrics': {
                'files': 75,
                'lines': 10000,
                'classes': 40,
                'functions': 150,
                'frameworks': ['Flask', 'SQLAlchemy']
            },
            'structure': {
                'has_tests': True,
                'entry_points': ['app.py', 'cli.py'],
                'packages': ['src', 'tests', 'utils']
            },
            'samples': [
                {'file': 'app.py', 'preview': 'from flask import Flask'}
            ]
        }
        
        # Evaluate
        result = evaluator.evaluate(analysis)
        
        # Verify
        self.assertEqual(result['complexity_level'], 'moderate')
        self.assertEqual(result['complexity_score'], 5.5)
        self.assertTrue(result['can_use_llm'])
        
        # Verify LLM was called with correct prompt
        mock_llm.invoke.assert_called_once()
        call_args = mock_llm.invoke.call_args[0][0]
        
        # Check that analysis data is in the prompt
        human_msg = call_args[1].content
        self.assertIn('75', human_msg)  # files
        self.assertIn('10000', human_msg)  # lines
        self.assertIn('Flask', human_msg)


if __name__ == '__main__':
    unittest.main()