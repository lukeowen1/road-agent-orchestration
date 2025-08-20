"""
workflow.py - Orchestrates the evaluation workflow using LangGraph
"""
import yaml
from typing import TypedDict, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from evaluator.codebase_analyser import PythonAnalyser
from evaluator.codebase_evaluator import ComplexityEvaluator


class WorkflowState(Dict[str, Any]):
    """State that flows through the workflow"""
    codebase_path: str
    analysis: Dict[str, Any]
    decision: Dict[str, Any]
    summary: str
    pass
   

def analyse_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node 1: Analyze the codebase"""
    config_path = state.get('config_path', 'config.yaml')
    analyser = PythonAnalyser(config_path)
    state['analysis'] = analyser.analyse_codebase(state['codebase_path'])
    return state


def evaluate_node(state:Dict[str, Any]) -> Dict[str, Any]:
    """Node 2: Evaluate complexity with LLM"""
    config_path = state.get('config_path', 'config.yaml')

    # load config for LLM settings 
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    llm_config = config['llm']
    llm = ChatOpenAI(
        model=llm_config['model'],
        temperature=llm_config['temperature'],
        max_tokens=llm_config.get('max_tokens')
    )

    evaluator = ComplexityEvaluator(llm)
    state['decision'] = evaluator.evaluate(state['analysis'])
    return state


def summary_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node 3: Create human-readable summary"""
    decision = state['decision']
    metrics = state['analysis']['metrics']
    
    summary = f"""
═══════════════════════════════════════════════════════════════
                    EVALUATION COMPLETE
═══════════════════════════════════════════════════════════════

Codebase: {state['codebase_path']}

Metrics:
• Files: {metrics['files']}
• Lines: {metrics['lines']}
• Frameworks: {', '.join(metrics['frameworks']) if metrics['frameworks'] else 'None'}

Decision:
• Complexity: {decision.get('complexity_level', 'unknown').upper()}
• Score: {decision.get('complexity_score', 0):.1f}/10
• Can Generate C4: {'YES' if decision.get('can_use_llm') else 'NO'}

Reasoning:
{decision.get('reasoning', 'No reasoning provided')}
"""
    
    state['summary'] = summary
    return state


def create_workflow():
    """Create the evaluation workflow"""
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("analyse", analyse_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("summary", summary_node)
    
    # Define flow
    workflow.set_entry_point("analyse")
    workflow.add_edge("analyse", "evaluate")
    workflow.add_edge("evaluate", "summary")
    workflow.add_edge("summary", END)
    
    return workflow.compile()