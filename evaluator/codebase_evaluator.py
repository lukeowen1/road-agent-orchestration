"""
evaluator.py - Uses LLM to evaluate if codebase is suitable for C4 generation
"""
import json
from typing import Dict, Optional
import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


class ComplexityEvaluator:
    """Evaluates codebase complexity using LLM"""
    
    def __init__(self, llm: Optional[ChatOpenAI] = None, config_path: str = "config.yaml"):
        """Initialize with an LLM instance"""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        if llm is None: 
            llm_config = self.config['llm']
            llm = ChatOpenAI(
                model=llm_config['model'],
                temperature=llm_config['temperature'],
                max_tokens=llm_config['max_tokens']
            )

        self.llm = llm or ChatOpenAI(model="gpt-4", temperature=0.1)
    
    def evaluate(self, analysis: Dict) -> Dict:
        """
        Evaluate if a codebase is suitable for C4 diagram generation
        
        Args:
            analysis: Output from PythonAnalyzer
            
        Returns:
            Decision dictionary with can_use_llm, complexity_level, etc.
        """
        prompt = self._create_prompt(analysis)
        response = self.llm.invoke(prompt)
        
        try:
            # Parse JSON response
            decision = json.loads(response.content)
        except:
            # Fallback if JSON parsing fails
            decision = self._create_fallback_decision(response.content)
        
        return decision
    
    def _create_prompt(self, analysis: Dict) -> list:
        """Create the evaluation prompt for the LLM"""
        metrics = analysis['metrics']
        structure = analysis['structure']
        samples = analysis['samples']
        
        system_message = self.config['prompts']['system_message'].format(
            simple_max_files=self.config['complexity']['simple']['max_files'],
            moderate_max_files=self.config['complexity']['moderate']['max_files']
        )

        # Build analysis summary using template
        summary = self.config['prompts']['evaluation_template'].format(
            files=metrics['files'],
            lines=metrics['lines'],
            classes=metrics['classes'],
            functions=metrics['functions'],
            frameworks=', '.join(metrics['frameworks']) if metrics['frameworks'] else 'None detected',
            has_tests=structure['has_tests'],
            entry_points=', '.join(structure['entry_points'][:3]) if structure['entry_points'] else 'None found',
            packages=len(structure['packages']),
            sample_file=samples[0]['file'] if samples else 'N/A',
            code_preview=samples[0]['preview'][:500] if samples else 'No samples available'
        )

        return [
            SystemMessage(content=system_message),
            HumanMessage(content=summary)
        ]
    
    def _create_fallback_decision(self, response_text: str) -> Dict:
        """Create a fallback decision if JSON parsing fails"""
        # Simple heuristic based on response text
        response_lower = response_text.lower()
        
        can_use = 'yes' in response_lower or 'suitable' in response_lower
        
        if 'simple' in response_lower:
            level = 'simple'
            score = 3.0
        elif 'complex' in response_lower:
            level = 'complex'
            score = 8.0
        else:
            level = 'moderate'
            score = 5.0
        
        return {
            "complexity_level": level,
            "complexity_score": score,
            "can_use_llm": can_use,
            "reasoning": "Failed to parse LLM response, used fallback heuristics",
            "confidence": 0.5
        }