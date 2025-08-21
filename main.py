"""
main.py - Run the codebase evaluator
"""
import sys
import os
from pathlib import Path
from evaluator.c4_generator import generate_c4_from_codebase
from evaluator.workflow import create_workflow


def evaluate_codebase(path: str, verbose: bool = True):
    """
    Evaluate a Python codebase for C4 diagram generation
    
    Args:
        path: Path to the codebase
        verbose: Print progress messages
        
    Returns:
        Decision dictionary
    """
    # Validate path
    codebase_path = Path(path)
    if not codebase_path.exists():
        raise ValueError(f"Path does not exist: {path}")
    
    if verbose:
        print(f"Evaluating: {codebase_path}")
        print("=" * 60)
    
    # Create and run workflow
    workflow = create_workflow()
    
    initial_state = {
        "codebase_path": str(codebase_path.absolute()),
        "analysis": {},
        "decision": {},
        "summary": ""
    }
    
    # Run the workflow
    result = workflow.invoke(initial_state)
    
    if verbose:
        print(result['summary'])
    
    # If suitable, generate C4 DSL
    decision = result.get('decision') if isinstance(result, dict) else None
    print(f"[DEBUG] decision: {decision} (type: {type(decision)})")  # Add this line
    if decision and isinstance(decision, dict) and decision.get('can_use_llm'):
        c4_result = generate_c4_from_codebase(
            codebase_path=str(codebase_path.absolute()),
            decision=decision,
            project_name=codebase_path.name,
            config_path="config.yaml",
            save_dsl=True
        )
        if verbose:
            print("\nC4 DSL Generation Result:")
            print("=" * 60)
            if isinstance(c4_result, dict) and c4_result.get("success", True):
                print(c4_result.get("dsl", "No DSL generated."))
            else:
                print(f"Error: {c4_result.get('error') if isinstance(c4_result, dict) else 'No result returned.'}")
    
    
    return result['decision']


def main():
    """Command-line interface"""
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_codebase>")
        print("\nExample:")
        print("  python main.py ./my_project")
        sys.exit(1)
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: Set OPENAI_API_KEY environment variable")
        print("export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)
    
    try:
        path = sys.argv[1]
        decision = evaluate_codebase(path)
        print(f"[DEBUG] Final decision: {decision} (type: {type(decision)})") 
        # Exit with appropriate code
        sys.exit(0 if decision and isinstance(decision, dict) and decision.get('can_use_llm') else 1)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()