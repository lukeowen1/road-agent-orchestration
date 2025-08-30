"""
workflow.py - Orchestrates the evaluation workflow using LangGraph
"""
import yaml
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
import os
from pathlib import Path
from langchain_core.tracers import LangChainTracer
from langchain.callbacks.manager import CallbackManager

from evaluator.codebase_analyser import PythonAnalyser
from evaluator.codebase_evaluator import ComplexityEvaluator
from evaluator.c4_generator import C4DiagramGenerator, StructurizrDSLValidator

# Set up tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "road-agent-orchestration"

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

def upload_structurizr_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node 4: Upload to Structurizr"""
    config_path = state.get('config_path', 'config.yaml')
    
    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    structurizr_config = config.get('structurizr', {})
    
    # Check if Structurizr is configured
    if not all([
        structurizr_config.get('api_key'),
        structurizr_config.get('api_secret'),
        structurizr_config.get('workspace_id')
    ]):
        print("Structurizr not configured. To enable upload:")
        print("1. Get API credentials from https://structurizr.com/help/web-api")
        print("2. Add to config.yaml:")
        print("structurizr:")
        print("api_key: 'your-key'")
        print("api_secret: 'your-secret'")
        print("workspace_id: 12345")
        
        state['structurizr_result'] = {
            'success': False,
            'message': 'Structurizr not configured',
            'manual_upload_url': 'https://structurizr.com/dsl'
        }
        return state
    
    c4_result = state.get('c4_result', {})
    dsl_content = c4_result.get('dsl')
    if not dsl_content:
        print("No DSL content to upload to Structurizr.")
        state['structurizr_result'] = {
            'success': False,
            'message': 'No DSL generated to upload'
        }
        return state

    print("Uploading to Structurizr...")
    print("=" * 60)

    # Save DSL file
    project_name = Path(state['codebase_path']).name
    dsl_file = f"{project_name.lower().replace(' ', '_')}_c4.dsl"
    Path(dsl_file).write_text(dsl_content)
    
    try:
        # Call your working upload script directly
        from cli.upload_dsl import StructurizrClient

        upload_client = StructurizrClient(config_path=config_path)
        
        success = upload_client.upload_dsl_file(
            dsl_file=dsl_file,
            config_path=config_path,
            open_browser=structurizr_config.get('auto_open_browser', True)
        )
        
        if success:
            workspace_url = f"https://structurizr.com/workspace/{structurizr_config['workspace_id']}"
            state['structurizr_result'] = {
                'upload_status': {'success': True},
                'urls': {'workspace': workspace_url}
            }
        else:
            # Capture error details for recovery agent
            cli_error = getattr(upload_client, 'last_cli_error', 'Upload failed via CLI')
            state['upload_error'] = cli_error
            state['dsl_file'] = dsl_file
            state['structurizr_result'] = {
                'upload_status': {'success': False},
                'message': 'Upload failed'
            }
    except Exception as e:
        # Capture error details for recovery agent  
        state['upload_error'] = str(e)
        state['dsl_file'] = dsl_file
        print(f"Upload failed: {e}")
        state['structurizr_result'] = {
            'upload_status': {'success': False},
            'error': str(e)
        }

    return state

def recovery_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node: Attempt to recover from upload failures"""
    print("Upload failed - attempting recovery...")
    
    from agents.upload_failure_recovery_agent import UploadFailureRecoveryAgent
    
    recovery_agent = UploadFailureRecoveryAgent()
    
    # Get the upload error details from the previous upload attempt
    upload_error = state.get('upload_error', 'Upload failed')
    print(f"Recovery agent received error: '{upload_error}'")
    dsl_file = Path(state.get('dsl_file', 'unknown.dsl'))
    
    with open(state.get('config_path', 'config.yaml'), 'r') as f:
        config = yaml.safe_load(f)
    
    recovery_result = recovery_agent.diagnose_and_retry(
        error_output=upload_error,
        dsl_file=dsl_file,
        config=config
    )
    
    state['recovery_result'] = recovery_result
    
    if recovery_result['recovery_successful']:
        print(f"Recovery successful using: {recovery_result.get('method', 'unknown')}")
        # Update the structurizr_result to reflect success
        state['structurizr_result']['upload_status']['success'] = True
    else:
        print("Recovery failed. Manual steps:")
        for instruction in recovery_result.get('instructions', []):
            print(f"  {instruction}")
    
    return state
    
def skip_upload_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node 4b: Skip upload if no DSL generated"""
    print("Skipping Structurizr upload - no DSL to upload")
    
    state['structurizr_result'] = {
        'success': False,
        'message': 'No DSL generated to upload'
    }
    return state

def summary_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node 5: Final summary"""
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    
    # Analysis summary
    metrics = state['analysis']['metrics']
    print(f"Codebase: {state['codebase_path']}")
    print(f"Files: {metrics['files']}, Lines: {metrics['lines']}")
    
    # Evaluation summary
    decision = state['decision']
    print(f"Evaluation:")
    print(f"Complexity: {decision.get('complexity_level', 'unknown').upper()}")
    print(f"Can generate C4: {'Yes' if decision.get('can_use_llm') else 'No'}")
    
    # C4 Generation summary
    if state.get('c4_result', {}).get('dsl'):
        print(f"C4 Generation:")
        print(f"Status: Success")
        if state.get('dsl_file'):
            print(f"DSL file: {state['dsl_file']}")
    else:
        print(f"C4 Generation: Skipped")
    
    # Structurizr summary
    structurizr_result = state.get('structurizr_result', {})
    if structurizr_result.get('success'):
        print(f"Structurizr:")
        print(f"Status: Uploaded")
        print(f"Workspace: {structurizr_result['urls']['workspace']}")
    elif structurizr_result.get('instructions'):
        print(f"Structurizr: Manual upload required")
        print(f"DSL Editor: {structurizr_result.get('workspace_url', 'https://structurizr.com/dsl')}")

    state['summary'] = "Pipeline execution complete"
    return state


def should_generate_c4(state: Dict[str, Any]) -> Literal["generate_c4", "skip_c4"]:
    """Conditional edge: decide whether to generate C4 diagrams"""
    decision = state.get('decision', {})
    can_generate = decision.get('can_use_llm', False)
    
    if can_generate:
        print("Routing to generate_c4")
        return "generate_c4"
    else:
        print("DEBUG: Routing to skip_c4")  
        return "skip_c4"

def should_upload_structurizr(state: Dict[str, Any]) -> Literal["upload_structurizr", "skip_upload"]:
    """Decide whether to upload to Structurizr"""
    c4_result = state.get('c4_result', {})
    dsl_content = c4_result.get('dsl')
    
    if dsl_content:
        print("Routing to upload_structurizr")
        return "upload_structurizr"
    else:
        print("Routing to skip_upload")
        return "skip_upload"
    
def should_attempt_recovery(state: Dict[str, Any]) -> Literal["recovery", "summary"]:
    upload_result = state.get('structurizr_result', {})
    if not upload_result.get('upload_status', {}).get('success', False):
        return "recovery"
    return "summary"

def create_workflow():
    """Create the evaluation workflow"""
    workflow = StateGraph(Dict[str, Any])

    # Add tracing callback
    tracer = LangChainTracer(project_name="road-agent-orchestration")
    callback_manager = CallbackManager([tracer])
    

    # Add nodes
    workflow.add_node("analyse", analyse_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("generate_c4", generate_c4_node)
    workflow.add_node("skip_c4", skip_c4_node)
    workflow.add_node("upload_structurizr", upload_structurizr_node)
    workflow.add_node("skip_upload", skip_upload_node)
    workflow.add_node("recovery_agent", recovery_agent_node)
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

    # recovery agent
    workflow.add_conditional_edges(
    "generate_c4",
    should_upload_structurizr,
    {
        "upload_structurizr": "upload_structurizr",
        "skip_upload": "skip_upload"
    }
    )

    # recovery routing after upload attempts
    workflow.add_conditional_edges(
    "upload_structurizr",
    should_attempt_recovery,
    {
        "recovery": "recovery_agent",
        "summary": "summary"
    }
    )

    # all paths lead to summary
    workflow.add_edge("skip_c4", "summary")
    workflow.add_edge("skip_upload", "summary")
    workflow.add_edge("recovery_agent", "summary")
    workflow.add_edge("summary", END)
    
    return workflow.compile()

