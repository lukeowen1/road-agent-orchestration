"""
test_c4_generator.py - Unit tests for the C4 diagram generator
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import yaml

from evaluator.c4_generator import (
    C4DiagramGenerator,
    StructurizrDSLValidator,
    generate_c4_from_codebase
)


class TestC4DiagramGenerator(unittest.TestCase):
    """Test the C4DiagramGenerator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create mock config
        self.mock_config = {
            'llm': {
                'model': 'gpt-3.5-turbo',
                'temperature': 0.1,
                'c4_temperature': 0.1,
                'c4_max_tokens': 4000
            },
            'analysis': {
                'skip_directories': ['venv', '__pycache__', '.git']
            }
        }
        
        # Write config
        self.config_path = self.test_path / 'config.yaml'
        with open(self.config_path, 'w') as f:
            yaml.dump(self.mock_config, f)
        
        # Create test codebase
        self.codebase_path = self.test_path / 'test_project'
        self.codebase_path.mkdir()
        
        # Add some Python files
        (self.codebase_path / 'main.py').write_text(
            'from fastapi import FastAPI\napp = FastAPI()\n'
        )
        (self.codebase_path / 'models.py').write_text(
            'class User:\n    pass\n'
        )
        
        # Add a venv directory that should be skipped
        venv_dir = self.codebase_path / 'venv'
        venv_dir.mkdir()
        (venv_dir / 'skip_me.py').write_text('# Should be skipped')
    
    def tearDown(self):
        """Clean up"""
        shutil.rmtree(self.test_dir)
    
    @patch('evaluator.c4_generator.ChatOpenAI')
    def test_generator_initialization(self, mock_chat):
        """Test generator initialization"""
        generator = C4DiagramGenerator(config_path=str(self.config_path))
        
        mock_chat.assert_called_once_with(
            model='gpt-3.5-turbo',
            temperature=0.1,
            max_tokens=4000
        )
    
    def test_read_entire_codebase(self):
        """Test reading all Python files from codebase"""
        generator = C4DiagramGenerator(
            llm=Mock(),
            config_path=str(self.config_path)
        )
        
        content = generator._read_entire_codebase(str(self.codebase_path))
        
        # Should have read main.py and models.py, but not venv/skip_me.py
        self.assertEqual(len(content), 2)
        self.assertIn('main.py', content)
        self.assertIn('models.py', content)
        self.assertNotIn('venv/skip_me.py', content)
        
        # Check content
        self.assertIn('FastAPI', content['main.py'])
        self.assertIn('User', content['models.py'])
    
    def test_create_c4_prompt(self):
        """Test prompt creation with codebase content"""
        generator = C4DiagramGenerator(
            llm=Mock(),
            config_path=str(self.config_path)
        )
        
        codebase_content = {
            'main.py': 'from fastapi import FastAPI\napp = FastAPI()',
            'models.py': 'class User:\n    pass'
        }
        
        messages = generator._create_c4_prompt(codebase_content, 'TestProject')
        
        self.assertEqual(len(messages), 2)
        
        # Check system message
        system_msg = messages[0].content
        self.assertIn('C4 architecture', system_msg)
        self.assertIn('Structurizr DSL', system_msg)
        
        # Check human message contains code
        human_msg = messages[1].content
        self.assertIn('TestProject', human_msg)
        self.assertIn('main.py', human_msg)
        self.assertIn('FastAPI', human_msg)
        self.assertIn('models.py', human_msg)
        self.assertIn('User', human_msg)
    
    def test_extract_dsl_with_code_blocks(self):
        """Test DSL extraction from markdown code blocks"""
        generator = C4DiagramGenerator(
            llm=Mock(),
            config_path=str(self.config_path)
        )
        
        response = '''Here's the DSL:
```dsl
workspace {
    model {
        user = person "User"
    }
}
```
That's the complete DSL.'''
        
        result = generator._extract_dsl(response)
        
        self.assertEqual(result.strip(), 'workspace {\n    model {\n        user = person "User"\n    }\n}')
    
    def test_extract_dsl_without_blocks(self):
        """Test DSL extraction without markdown blocks"""
        generator = C4DiagramGenerator(
            llm=Mock(),
            config_path=str(self.config_path)
        )
        
        response = '''The DSL is:
        workspace {
            model {
                user = person "User"
            }
        }
        End of DSL'''
        
        result = generator._extract_dsl(response)
        
        self.assertIn('workspace', result)
        self.assertIn('model', result)
        self.assertIn('person "User"', result)
    
    def test_extract_dsl_with_nested_braces(self):
        """Test DSL extraction with nested braces"""
        generator = C4DiagramGenerator(
            llm=Mock(),
            config_path=str(self.config_path)
        )
        
        response = '''workspace {
            model {
                system = softwareSystem "System" {
                    container "API" {
                        component "Handler"
                    }
                }
            }
        }
        Some extra text after'''
        
        result = generator._extract_dsl(response)
        
        # Should extract complete workspace
        self.assertTrue(result.startswith('workspace'))
        self.assertTrue(result.endswith('}'))
        self.assertNotIn('extra text', result)
    
    @patch('evaluator.c4_generator.ChatOpenAI')
    
    def test_generate_c4_dsl_full_flow(self, mock_chat_class):
        """Test complete DSL generation flow"""
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = '''workspace {
        model {
            user = person "User"
            system = softwareSystem "TestProject"
            user -> system "Uses"
        }
        views {
            systemContext system {
                include *
            }
        }
    }'''
        
        mock_llm = Mock()
        mock_llm.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_llm
        
        generator = C4DiagramGenerator(config_path=str(self.config_path))
        result = generator.generate_c4_dsl(str(self.codebase_path), "TestProject")
        
        self.assertIn('dsl', result)
        self.assertIn('workspace', result['dsl'])
        self.assertEqual(result['files_processed'], 2)  # main.py and models.py
        self.assertEqual(result['project_name'], 'TestProject')
    
    def test_read_codebase_with_encoding_errors(self):
        """Test handling files with encoding issues"""
        generator = C4DiagramGenerator(
            llm=Mock(),
            config_path=str(self.config_path)
        )
        
        # Create file with problematic encoding
        bad_file = self.codebase_path / 'bad_encoding.py'
        bad_file.write_bytes(b'# \xff\xfe Invalid encoding\nclass Test:\n    pass')
        
        # Should not crash
        content = generator._read_entire_codebase(str(self.codebase_path))
        
        # Should still read the good files
        self.assertIn('main.py', content)
        self.assertIn('models.py', content)


class TestStructurizrDSLValidator(unittest.TestCase):
    """Test the StructurizrDSLValidator class"""
    
    def test_validate_valid_dsl(self):
        """Test validation of valid DSL"""
        validator = StructurizrDSLValidator()
        
        valid_dsl = '''workspace {
        model {
            user = person "User"
            system = softwareSystem "System"
        }
        views {
            systemContext system {
                include *
            }
        }
    }'''
        
        result = validator.validate_dsl(valid_dsl)
        
        self.assertTrue(result['is_valid'])
        self.assertTrue(result['has_workspace'])
        self.assertTrue(result['has_model'])
        self.assertTrue(result['has_views'])
        self.assertEqual(len(result['errors']), 0)
    
    def test_validate_missing_workspace(self):
        """Test validation with missing workspace"""
        validator = StructurizrDSLValidator()
        
        invalid_dsl = '''model {
        user = person "User"
    }'''
        
        result = validator.validate_dsl(invalid_dsl)
        
        self.assertFalse(result['is_valid'])
        self.assertFalse(result['has_workspace'])
        self.assertIn("Missing 'workspace'", result['errors'][0])
    
    def test_validate_missing_model(self):
        """Test validation with missing model"""
        validator = StructurizrDSLValidator()
        
        invalid_dsl = '''workspace {
        views {
            # some views
        }
    }'''
        
        result = validator.validate_dsl(invalid_dsl)
        
        self.assertFalse(result['is_valid'])
        self.assertFalse(result['has_model'])
        self.assertIn("Missing 'model'", result['errors'][0])
    
    def test_validate_missing_views(self):
        """Test validation with missing views (warning only)"""
        validator = StructurizrDSLValidator()
        
        dsl_no_views = '''workspace {
        model {
            user = person "User"
        }
    }'''
        
        result = validator.validate_dsl(dsl_no_views)
        
        self.assertTrue(result['is_valid'])  # Still valid, just warning
        self.assertFalse(result['has_views'])
        self.assertIn("Missing 'views'", result['warnings'][0])
    
    def test_validate_mismatched_braces(self):
        """Test validation with mismatched braces"""
        validator = StructurizrDSLValidator()
        
        invalid_dsl = '''workspace {
        model {
            user = person "User"
        }
    }
    }'''  # Extra closing brace
        
        result = validator.validate_dsl(invalid_dsl)
        
        self.assertFalse(result['is_valid'])
        self.assertIn('Mismatched braces', result['errors'][0])
    
    def test_validate_no_software_system(self):
        """Test validation with no software system (warning)"""
        validator = StructurizrDSLValidator()
        
        dsl = '''workspace {
        model {
            user = person "User"
        }
        views { }
    }'''
        
        result = validator.validate_dsl(dsl)
        
        self.assertTrue(result['is_valid'])
        self.assertIn('No software system', result['warnings'][0])
    
    def test_enhance_dsl_add_styles(self):
        """Test adding default styles to DSL"""
        validator = StructurizrDSLValidator()
        
        dsl_without_styles = '''workspace {
        model {
            user = person "User"
        }
        views {
            systemContext system {
                include *
            }
        }
    }'''
        
        enhanced = validator.enhance_dsl(dsl_without_styles, add_styles=True)
        
        self.assertIn('styles', enhanced)
        self.assertIn('element "Software System"', enhanced)
        self.assertIn('element "Person"', enhanced)
        self.assertIn('shape person', enhanced)
    
    def test_enhance_dsl_existing_styles(self):
        """Test not adding styles when they exist"""
        validator = StructurizrDSLValidator()
        
        dsl_with_styles = '''workspace {
        model { }
        views {
            styles {
                element "Person" {
                    shape person
                }
            }
        }
    }'''
        
        enhanced = validator.enhance_dsl(dsl_with_styles, add_styles=True)
        
        # Should not duplicate styles
        self.assertEqual(enhanced.count('styles'), 1)
    
    def test_enhance_dsl_no_views(self):
        """Test enhancement when no views section"""
        validator = StructurizrDSLValidator()
        
        dsl = '''workspace {
        model {
            user = person "User"
        }
    }'''
        
        enhanced = validator.enhance_dsl(dsl, add_styles=True)
        
        # Should not add styles without views
        self.assertNotIn('styles', enhanced)


class TestGenerateC4FromCodebase(unittest.TestCase):
    """Test the main generation function"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create config
        self.config_path = self.test_path / 'config.yaml'
        config = {
            'llm': {
                'model': 'gpt-3.5-turbo',
                'c4_temperature': 0.1,
                'c4_max_tokens': 4000
            },
            'analysis': {
                'skip_directories': ['venv']
            }
        }
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
        
        # Create test codebase
        self.codebase_path = self.test_path / 'project'
        self.codebase_path.mkdir()
        (self.codebase_path / 'main.py').write_text('print("hello")')
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_generate_with_complex_codebase(self):
        """Test generation rejection for complex codebase"""
        decision = {
            'can_use_llm': False,
            'complexity_level': 'complex'
        }
        
        result = generate_c4_from_codebase(
            str(self.codebase_path),
            decision,
            config_path=str(self.config_path),
            save_dsl=False
        )
        
        self.assertFalse(result['success'])
        self.assertIn('too complex', result['error'])
        self.assertEqual(result['complexity_level'], 'complex')
    
    @patch('evaluator.c4_generator.C4DiagramGenerator')
    def test_generate_with_simple_codebase(self, mock_generator_class):
        """Test successful generation for simple codebase"""
        # Mock generator
        mock_generator = Mock()
        mock_generator.generate_c4_dsl.return_value = {
            'dsl': 'workspace { model { } }',
            'files_processed': 1,
            'project_name': 'project'
        }
        mock_generator_class.return_value = mock_generator
        
        decision = {
            'can_use_llm': True,
            'complexity_level': 'simple'
        }
        
        result = generate_c4_from_codebase(
            str(self.codebase_path),
            decision,
            project_name='TestProject',
            config_path=str(self.config_path),
            save_dsl=False
        )
        
        self.assertTrue(result['success'])
        self.assertIn('dsl', result)
        self.assertEqual(result['files_processed'], 1)
        self.assertEqual(result['project_name'], 'TestProject')
    
    @patch('evaluator.c4_generator.C4DiagramGenerator')
    def test_generate_with_save_dsl(self, mock_generator_class):
        """Test DSL file saving"""
        # Mock generator
        mock_generator = Mock()
        mock_generator.generate_c4_dsl.return_value = {
            'dsl': 'workspace { model { } views { } }',
            'files_processed': 1,
            'project_name': 'TestProject'
        }
        mock_generator_class.return_value = mock_generator
        
        decision = {'can_use_llm': True}
        
        result = generate_c4_from_codebase(
            str(self.codebase_path),
            decision,
            project_name='TestProject',
            config_path=str(self.config_path),
            save_dsl=True
        )
        
        # Check file was saved
        expected_file = self.codebase_path / 'TestProject_c4.dsl'
        self.assertTrue(expected_file.exists())
        self.assertEqual(result['dsl_file'], str(expected_file))
        
        # Check content
        content = expected_file.read_text()
        self.assertIn('workspace', content)
    
    def test_generate_with_none_decision(self):
        """Test handling of None decision"""
        result = generate_c4_from_codebase(
            str(self.codebase_path),
            None,  # No decision provided
            config_path=str(self.config_path)
        )
        
        self.assertFalse(result['success'])
        self.assertIn('too complex', result['error'])


if __name__ == '__main__':
    unittest.main()