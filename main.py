"""
main.py - Run the codebase evaluator
"""
import sys
import os
from pathlib import Path
from workflow import create_workflow


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
        print(f"🔍 Evaluating: {codebase_path}")
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
        
        # Exit with appropriate code
        sys.exit(0 if decision.get('can_use_llm') else 1)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()