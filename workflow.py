"""
workflow.py - Orchestrates the evaluation workflow using LangGraph
"""
from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from codebase_analyser import PythonAnalyzer
from codebase_evaluator import ComplexityEvaluator


class WorkflowState(TypedDict):
    """State that flows through the workflow"""
    codebase_path: str
    analysis: Dict[str, Any]
    decision: Dict[str, Any]
    summary: str


def analyze_node(state: WorkflowState) -> WorkflowState:
    """Node 1: Analyze the codebase"""
    analyzer = PythonAnalyzer()
    state['analysis'] = analyzer.analyze_codebase(state['codebase_path'])
    return state


def evaluate_node(state: WorkflowState) -> WorkflowState:
    """Node 2: Evaluate complexity with LLM"""
    # Get LLM from state or create default
    llm = ChatOpenAI(model="gpt-4", temperature=0.1)
    evaluator = ComplexityEvaluator(llm)
    state['decision'] = evaluator.evaluate(state['analysis'])
    return state


def summary_node(state: WorkflowState) -> WorkflowState:
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
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("summary", summary_node)
    
    # Define flow
    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "evaluate")
    workflow.add_edge("evaluate", "summary")
    workflow.add_edge("summary", END)
    
    return workflow.compile()