"""
A script to generate DSL for a codebase deemed simple from our evaluator script.
"""

import yaml 
from typing import Dict, List, Optional 
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pathlib import Path

class C4DiagramGenerator:
    """Generates C4 diagrams in Structurizr DSL format"""

    def __init__(self, llm: Optional[ChatOpenAI] = None, config_path: str = "config.yaml"):
        """Initilaise with LLM and configuration"""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        if llm is None:
            llm_config = self.config['llm']
            llm = ChatOpenAI(
                model=llm_config['model'],
                temperature=llm_config.get('c4_temperature', 0.1),
                max_tokens=llm_config.get('c4_max_tokens', 4000)
            )

        self.llm = llm

    def generate_c4_dsl(self, codebase_path: str, project_name: str = "System") -> Dict:
        """
        Generate C4 diagrams by feeding entire codebase to LLM
        
        Args:
            codebase_path: Path to the Python codebase
            project_name: Name for the system
            
        Returns:
            Dictionary with DSL and metadata
        """
        # Read the entire codebase
        codebase_content = self._read_entire_codebase(codebase_path)
        
        # Create prompt with full codebase
        prompt = self._create_c4_prompt(codebase_content, project_name)
        
        # Get DSL from LLM
        response = self.llm.invoke(prompt)
        dsl_content = response.content
        
        # Extract and clean DSL
        dsl = self._extract_dsl(dsl_content)
        
        return {
            "dsl": dsl,
            "raw_response": dsl_content,
            "files_processed": len(codebase_content),
            "project_name": project_name
        }
    
    def _read_entire_codebase(self, codebase_path: str) -> Dict[str, str]:
        """
        Read all Python files from the codebase
        
        Args:
            codebase_path: Path to the codebase
            
        Returns:
            Dictionary mapping file paths to their contents
        """
        base_path = Path(codebase_path)
        codebase_content = {}
        
        # Get skip directories from config
        skip_dirs = set(self.config['analysis']['skip_directories'])
        
        # Read all Python files
        for py_file in base_path.rglob('*.py'):
            # Skip unwanted directories
            if any(skip_dir in py_file.parts for skip_dir in skip_dirs):
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Store with relative path as key
                    relative_path = py_file.relative_to(base_path)
                    codebase_content[str(relative_path)] = content
            except Exception as e:
                print(f"Warning: Could not read {py_file}: {e}")
                continue
        
        return codebase_content
    
    def _create_c4_prompt(self, codebase_content: Dict[str, str], project_name: str) -> list:
        """Create the prompt with the entire codebase"""
        
        system_prompt = """You are an expert software architect who creates C4 architecture diagrams.
        You will be given the COMPLETE source code of a Python application.
        Analyse the code and generate a comprehensive Structurizr DSL file that accurately models the application architecture.

        **IMPORTANT STRUCTURIZR DSL RULES:**
        - Do NOT use variable assignments for containers or components (e.g., do NOT write `foo = container ...`).
        - Define all containers INSIDE their parent softwareSystem block.
        - Define all components INSIDE their parent container block.
        - Define relationships between components INSIDE the container block.
        - Do NOT reference components or containers at the top level.
        - Only use valid Structurizr DSL syntax.

        **EXAMPLE:**

        workspace {
            model {
                user = person "User"
                mainSystem = softwareSystem "<Main System Name>" {
                    # Define containers found in the codebase
                    containerA = container "<Container A Name>" {
                        # Define components found in this container
                        componentA = component "<Component A Name>" {
                            description "<What this component does>"
                        }
                        componentB = component "<Component B Name>" {
                            description "<What this component does>"
                        }
                        # Relationships between components (use identifiers)
                        componentA -> componentB "<Relationship description>"
                    }
                    containerB = container "<Container B Name>" {
                        # ...more components...
                    }
                    # Relationships between containers (use identifiers)
                    containerA -> containerB "<Relationship description>"
                }
                # Define external systems/services if found
                externalSystem = softwareSystem "<External System Name>"
                database = softwareSystem "<Database Name>"
                # Relationships from user and containers to systems/services
                user -> mainSystem "<How user interacts>"
                containerA -> externalSystem "<Relationship description>"
                containerA -> database "<Relationship description>"
            }
            views {
                systemContext mainSystem {
                    include *
                    autoLayout
                }
                container mainSystem {
                    include *
                    autoLayout
                }
                # For each container, add a component view
                component containerA {
                    include *
                    autoLayout
                }
                styles {
                    element "Software System" {
                        background #1168bd
                        color #ffffff
                    }
                    element "Container" {
                        background #438dd5
                        color #ffffff
                    }
                    element "Component" {
                        background #85bbf0
                        color #000000
                    }
                    element "Person" {
                        shape person
                        background #08427b
                        color #ffffff
                    }
                    element "Database" {
                        shape cylinder
                    }
                    element "External System" {
                        background #999999
                        color #ffffff
                    }
                }
            }
        }

        Base your architecture ENTIRELY on the actual code provided, not on assumptions.
        Generate ONLY the Structurizr DSL code, starting with 'workspace' and ending with the closing brace.
        Make sure the DSL is complete, valid, and ready to use.
        """
        # Build the complete codebase message
        codebase_message = f"Project Name: {project_name}\n\n"
        codebase_message += "=" * 60 + "\n"
        codebase_message += "COMPLETE PYTHON CODEBASE:\n"
        codebase_message += "=" * 60 + "\n\n"
        
        # Add all files with clear separation
        for file_path, content in codebase_content.items():
            codebase_message += f"### File: {file_path}\n"
            codebase_message += "```python\n"
            codebase_message += content
            codebase_message += "\n```\n\n"
        
        codebase_message += "=" * 60 + "\n"
        codebase_message += """
        Based on the complete codebase above, generate a Structurizr DSL that:
        1. Accurately represents the architecture found in the code
        2. Includes all major components and their relationships
        3. Uses meaningful names from the actual code
        4. Creates clear System Context, Container, and Component views
        5. Is syntactically correct and complete

        Generate the Structurizr DSL:"""
        
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=codebase_message)
        ]
    
    def _extract_dsl(self, response: str) -> str:
        """Extract clean DSL from LLM response"""
        # Remove markdown code blocks if present
        if "```" in response:
            import re
            # Look for code blocks
            pattern = r'```(?:dsl|structurizr|plaintext|workspace)?\n?(.*?)```'
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                return matches[0].strip()
        
        # If no code blocks, look for workspace definition
        if "workspace" in response:
            # Find from workspace to the end
            start = response.find("workspace")
            if start != -1:
                # Find the last closing brace that matches the workspace
                content = response[start:]
                # Count braces to find the complete workspace
                brace_count = 0
                end_pos = 0
                for i, char in enumerate(content):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_pos = i + 1
                            break
                
                if end_pos > 0:
                    return content[:end_pos].strip()
        
        # Return as is if no special formatting found
        return response.strip()
    
class StructurizrDSLValidator:
    """Validates Structurizr DSL output"""
    
    @staticmethod
    def validate_dsl(dsl: str) -> Dict:
        """
        Validate the DSL structure
        
        Returns:
            Dictionary with validation results
        """
        validation = {
            "is_valid": True,
            "has_workspace": False,
            "has_model": False,
            "has_views": False,
            "errors": [],
            "warnings": []
        }
        
        # Check for required sections
        if "workspace" not in dsl:
            validation["errors"].append("Missing 'workspace' definition")
            validation["is_valid"] = False
        else:
            validation["has_workspace"] = True
        
        if "model" not in dsl:
            validation["errors"].append("Missing 'model' section")
            validation["is_valid"] = False
        else:
            validation["has_model"] = True
        
        if "views" not in dsl:
            validation["warnings"].append("Missing 'views' section - diagrams won't be visible")
            validation["has_views"] = False
        else:
            validation["has_views"] = True
        
        # Check for basic syntax
        open_braces = dsl.count("{")
        close_braces = dsl.count("}")
        if open_braces != close_braces:
            validation["errors"].append(f"Mismatched braces: {open_braces} open, {close_braces} close")
            validation["is_valid"] = False
        
        # Check for at least one system
        if "softwareSystem" not in dsl and "software_system" not in dsl:
            validation["warnings"].append("No software system defined")
        
        return validation
    
    @staticmethod
    def enhance_dsl(dsl: str, add_styles: bool = True) -> str:
        """
        Enhance DSL with default styles if missing
        
        Args:
            dsl: The DSL to enhance
            add_styles: Whether to add default styles
            
        Returns:
            Enhanced DSL
        """
        # Add default styles if not present
        if add_styles and "styles" not in dsl and "views" in dsl:
            styles = """
            styles {
                element "Software System" {
                    background #1168bd
                    color #ffffff
                }
                element "Container" {
                    background #438dd5
                    color #ffffff
                }
                element "Component" {
                    background #85bbf0
                    color #000000
                }
                element "Person" {
                    shape person
                    background #08427b
                    color #ffffff
                }
                element "Database" {
                    shape cylinder
                }
                element "External System" {
                    background #999999
                    color #ffffff
                }
            }"""
            
            # Find the views closing brace and insert styles after it
            views_end = dsl.rfind("views")
            if views_end != -1:
                # Find the closing brace for views
                brace_count = 0
                start_counting = False
                for i in range(views_end, len(dsl)):
                    if dsl[i] == '{':
                        start_counting = True
                        brace_count += 1
                    elif dsl[i] == '}' and start_counting:
                        brace_count -= 1
                        if brace_count == 0:
                            # Insert styles after views closing brace
                            dsl = dsl[:i+1] + "\n" + styles + "\n" + dsl[i+1:]
                            break
        
        return dsl


def generate_c4_from_codebase(
    codebase_path: str,
    decision: Dict,
    project_name: str = None,
    config_path: str = "config.yaml",
    save_dsl: bool = True
) -> Dict:
    """
    Generate C4 diagrams from actual codebase (not metrics)
    
    Args:
        codebase_path: Path to Python codebase
        decision: Output from ComplexityEvaluator
        project_name: Name for the system
        config_path: Path to configuration file
        save_dsl: Whether to save DSL to file
        
    Returns:
        Dictionary with DSL and validation results
    """
    
    # Default project name from directory
    if project_name is None:
        project_name = Path(codebase_path).name
    
    # Check if LLM can handle this codebase
    if not (decision and decision.get('can_use_llm', False)):
        return {
            "success": False,
            "error": "Codebase is too complex for LLM-based C4 generation",
            "complexity_level": (decision or {}).get('complexity_level', 'unknown')
        }
    
    print(f"Reading entire codebase from: {codebase_path}")
    
    # Generate C4 DSL from the actual code
    generator = C4DiagramGenerator(config_path=config_path)
    result = generator.generate_c4_dsl(codebase_path, project_name)
    
    print(f"Processed {result['files_processed']} Python files")
    print("Generating C4 architecture from code...")

    # Validate the generated DSL
    validator = StructurizrDSLValidator()
    validation = validator.validate_dsl(result['dsl'])

    # Enhance DSL if valid
    if validation['is_valid']:
        result['dsl'] = validator.enhance_dsl(result['dsl'])

    # Optionally save DSL to file
    if save_dsl:
        dsl_path = Path(codebase_path) / f"{project_name}_c4.dsl"
        print(dsl_path)
        try:
            with open(dsl_path, "w") as f:
                f.write(result['dsl'])
            result['dsl_file'] = str(dsl_path)
        except Exception as e:
            result['dsl_file'] = None
            result['save_error'] = str(e)

     # Always return a result dictionary!
    return {
        "success": validation['is_valid'],
        "dsl": result['dsl'],
        "validation": validation,
        "files_processed": result['files_processed'],
        "project_name": project_name,
        "dsl_file": result.get('dsl_file'),
        "save_error": result.get('save_error')
    }