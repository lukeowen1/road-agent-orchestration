"""
evaluator.py - Uses LLM to evaluate if codebase is suitable for C4 generation
"""
import json
from typing import Dict, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


class ComplexityEvaluator:
    """Evaluates codebase complexity using LLM"""
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """Initialize with an LLM instance"""
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
        
        system_message = """You are an expert architect evaluating if a Python codebase 
        is simple enough for AI-generated C4 diagrams.
        
        Consider:
        - Simple: < 50 files, clear structure, single service
        - Moderate: 50-150 files, few services, standard patterns  
        - Complex: > 150 files, microservices, unclear boundaries
        
        Respond with JSON:
        {
            "complexity_level": "simple|moderate|complex",
            "complexity_score": 0-10,
            "can_use_llm": true|false,
            "reasoning": "explanation",
            "confidence": 0-1
        }"""
        
        # Build analysis summary
        summary = f"""
        Python Codebase Analysis:
        
        Metrics:
        - Files: {metrics['files']}
        - Lines: {metrics['lines']}
        - Classes: {metrics['classes']}
        - Functions: {metrics['functions']}
        - Frameworks: {', '.join(metrics['frameworks']) if metrics['frameworks'] else 'None detected'}
        
        Structure:
        - Has tests: {structure['has_tests']}
        - Entry points: {', '.join(structure['entry_points'][:3]) if structure['entry_points'] else 'None found'}
        - Packages: {len(structure['packages'])} packages found
        
        Code Sample from {samples[0]['file'] if samples else 'N/A'}:
        ```python
        {samples[0]['preview'][:500] if samples else 'No samples available'}
        ```
        
        Question: Can an LLM effectively generate C4 diagrams for this codebase?
        """
        
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