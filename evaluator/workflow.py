"""
workflow.py - Orchestrates the evaluation workflow using LangGraph
"""
import yaml
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from evaluator.codebase_analyser import PythonAnalyser
from evaluator.codebase_evaluator import ComplexityEvaluator
from evaluator.c4_generator import C4DiagramGenerator, StructurizrDSLValidator


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

def generate_c4_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node 3: Generate C4 diagrams from the actual codebase"""
    config_path = state.get('config_path', 'config.yaml')
    project_name = state.get('project_name', 'System')
    codebase_path = state['codebase_path']
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    llm_config = config['llm']
    llm = ChatOpenAI(
        model=llm_config['model'],
        temperature=llm_config.get('c4_temperature', 0.1),
        max_tokens=llm_config.get('c4_max_tokens', 4000)
    )
    
    print(f"Reading entire codebase from: {codebase_path}")
    
    # Generate C4 from the codebase
    generator = C4DiagramGenerator(llm, config_path)
    result = generator.generate_c4_dsl(codebase_path, project_name)
    
    print(f"Fed {result['files_processed']} files to LLM")
    print("LLM is analyzing the complete code...")
    
    # Validate the generated DSL
    validator = StructurizrDSLValidator()
    validation = validator.validate_dsl(result['dsl'])
    
    # Enhance DSL if valid
    if validation['is_valid']:
        result['dsl'] = validator.enhance_dsl(result['dsl'])
    
    state['c4_result'] = {
        'dsl': result['dsl'],
        'validation': validation,
        'files_processed': result['files_processed']
    }
    
    return state


def skip_c4_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node 3b: Skip C4 generation if codebase is too complex"""
    decision = state.get('decision') or {}
    state['c4_result'] = {
        'dsl': None,
        'validation': {
            'is_valid': False,
            'errors': ['Codebase too complex for automated C4 generation']
        },
        'metadata': {
            'skipped': True,
            'reason': decision.get('reasoning', 'Complexity threshold exceeded')
        }
    }
    return state

def summary_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node 3: Create human-readable summary"""
    decision = state.get('decision') or {}
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

def should_generate_c4(state: Dict[str, Any]) -> Literal["generate_c4", "skip_c4"]:
    """Conditional edge: decide whether to generate C4 diagrams"""
    if (state.get('decision') or {}).get('can_use_llm', False):
        return "generate_c4"
    return "skip_c4"

def create_workflow():
    """Create the evaluation workflow"""
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("analyse", analyse_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("generate_c4", generate_c4_node)
    workflow.add_node("skip_c4", skip_c4_node)
    workflow.add_node("summary", summary_node)

    # Define flow
    workflow.set_entry_point("analyse")
    workflow.add_edge("analyse", "evaluate")

    # Conditional edge based on evaluation
    workflow.add_conditional_edges(
        "evaluate",
        should_generate_c4,
        {
            "generate_c4": "generate_c4",
            "skip_c4": "skip_c4"
        }
    )

    workflow.add_edge("generate_c4", "summary")
    workflow.add_edge("skip_c4", "summary")
    workflow.add_edge("summary", END)
    
    return workflow.compile()

