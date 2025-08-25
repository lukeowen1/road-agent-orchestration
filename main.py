"""
main.py - Run the codebase evaluator with optional Structurizr upload
"""
import sys
import os
import yaml
from pathlib import Path
from evaluator.c4_generator import generate_c4_from_codebase
from evaluator.workflow import create_workflow

# Import Structurizr components if available
try:
    from structurizr_client import upload_dsl_to_structurizr
    STRUCTURIZR_AVAILABLE = True
except ImportError:
    STRUCTURIZR_AVAILABLE = False
    print("Note: Structurizr client not found. DSL will be generated but not uploaded.")

# Import the DSL upload agent if available
try:
    from agents.dsl_upload_agent import DSLUploadAgent
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False
    print("Note: DSL upload agent not found. DSL will be generated but not uploaded.")

def evaluate_codebase(path: str, verbose: bool = True, upload_to_structurizr: bool = False):
    """
    Evaluate a Python codebase for C4 diagram generation
    
    Args:
        path: Path to the codebase
        verbose: Print progress messages
        upload_to_structurizr: Whether to upload DSL to Structurizr
        
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
        "summary": "",
        "config_path": "config.yaml"  # Add config_path to state
    }
    
    # Run the workflow
    result = workflow.invoke(initial_state)
    
    if verbose:
        print(result['summary'])
    
    # If suitable, generate C4 DSL
    decision = result.get('decision') if isinstance(result, dict) else None
    
    if decision and isinstance(decision, dict) and decision.get('can_use_llm'):
        if verbose:
            print("Generating C4 DSL...")
            print("=" * 60)
        
        c4_result = generate_c4_from_codebase(
            codebase_path=str(codebase_path.absolute()),
            decision=decision,
            project_name=codebase_path.name,
            config_path="config.yaml",
            save_dsl=True
        )
        
        # Add c4_result to the state for potential Structurizr upload
        result['c4_result'] = c4_result if c4_result else {'dsl': None, 'success': False}
        
        if verbose and isinstance(c4_result, dict):
            if c4_result.get("success"):
                print(f"C4 DSL generated successfully!")
                if c4_result.get("dsl_file"):
                    print(f"Saved to: {c4_result['dsl_file']}")
                
                # Use agent to upload if requested
                if upload_to_structurizr and AGENT_AVAILABLE:
                    upload_with_agent(c4_result, verbose)
                elif upload_to_structurizr and not AGENT_AVAILABLE:
                    print("Upload agent not available")
                    print("Ensure dsl_upload_agent.py is in the same directory")
                    manual_upload_instructions()
            else:
                print(f"Error: {c4_result.get('error', 'Failed to generate DSL')}")
    else:
        if verbose:
            reason = "evaluation failed" if not decision else "codebase too complex"
            print(f"Skipping C4 generation - {reason}")
        
        # Ensure c4_result exists
        if 'c4_result' not in result:
            result['c4_result'] = {
                'dsl': None,
                'success': False,
                'error': 'C4 generation skipped'
            }
    
    return result.get('decision', {})

def upload_with_agent(c4_result: dict, verbose: bool = True):
    """
    Use the DSL upload agent to upload to Structurizr
    
    Args:
        c4_result: Result from C4 generation
        verbose: Print progress messages
    """
    if verbose:
        print("Activating DSL Upload Agent...")
        print("=" * 60)
    
    try:
        # Initialize the agent
        agent = DSLUploadAgent(verbose=verbose)
        
        # Get the DSL file path
        dsl_file = c4_result.get("dsl_file")
        if not dsl_file:
            # Try to construct it from project name
            project_name = c4_result.get("project_name", "system")
            dsl_file = f"{project_name.lower().replace(' ', '_')}_c4.dsl"
        
        # Check if file exists
        dsl_path = Path(dsl_file)
        if not dsl_path.exists():
            if verbose:
                print(f"DSL file not found: {dsl_file}")
                manual_upload_instructions()
            return
        
        # Upload using the agent
        upload_result = agent.upload_dsl_file(dsl_path)
        
        if not upload_result.get("success"):
            if verbose:
                print("Agent upload failed")
                if upload_result.get("error"):
                    print(f"Error: {upload_result['error']}")
                manual_upload_instructions()
                
    except Exception as e:
        if verbose:
            print(f"Agent error: {str(e)}")
            manual_upload_instructions()

def manual_upload_instructions():
    """Print manual upload instructions"""
    print("Manual Upload Instructions:")
    print("1. Copy the content of the generated .dsl file")
    print("2. Go to https://structurizr.com/dsl")
    print("3. Paste the content and click 'Render'")
    print("Or use the upload script directly:")
    print("python upload_dsl.py <your_file>_c4.dsl")

def upload_dsl_to_structurizr_wrapper(dsl_content: str, project_name: str, verbose: bool = True):
    """
    Wrapper to upload DSL to Structurizr
    
    Args:
        dsl_content: The DSL content to upload
        project_name: Project name for display
        verbose: Print progress messages
    """
    if verbose:
        print("Attempting Structurizr upload...")
        print("=" * 60)
    
    # Check if Structurizr is configured
    config_path = "config.yaml"
    if Path(config_path).exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            structurizr_config = config.get('structurizr', {})
        
        if all([
            structurizr_config.get('api_key'),
            structurizr_config.get('api_secret'),
            structurizr_config.get('workspace_id')
        ]):
            try:
                # Upload to Structurizr
                result = upload_dsl_to_structurizr(
                    dsl_content=dsl_content,
                    config_path=config_path,
                    open_browser=structurizr_config.get('auto_open_browser', True)
                )
                
                if result.get('upload_status', {}).get('success'):
                    print("Upload successful!")
                    if result.get('urls'):
                        print(f"View at: {result['urls'].get('workspace', 'Structurizr workspace')}")
                else:
                    print("Manual upload instructions:")
                    instructions = result.get('instructions', [])
                    if instructions:
                        for instruction in instructions:
                            print(f"{instruction}")
                    else:
                        print("1. Copy the generated .dsl file content")
                        print("2. Go to https://structurizr.com/dsl")
                        print("3. Paste and click 'Render'")
                        
            except Exception as e:
                if verbose:
                    print(f"Upload error: {str(e)}")
                    print("You can manually upload the DSL:")
                    print("1. Copy the generated .dsl file content")
                    print("2. Go to https://structurizr.com/dsl")
                    print("3. Paste and click 'Render'")
        else:
            if verbose:
                missing = []
                if not structurizr_config.get('api_key'):
                    missing.append('api_key')
                if not structurizr_config.get('api_secret'):
                    missing.append('api_secret')
                if not structurizr_config.get('workspace_id'):
                    missing.append('workspace_id')
                
                print(f"Structurizr not fully configured (missing: {', '.join(missing)})")
                print("To enable automatic upload:")
                print("1. Get API credentials from https://structurizr.com/help/web-api")
                print("2. Add to config.yaml:")
                print("structurizr:")
                print("api_key: 'your-key'")
                print("api_secret: 'your-secret'")
                print("workspace_id: 12345")
                print("For now, you can manually upload:")
                print("1. Copy the generated .dsl file content")
                print("2. Go to https://structurizr.com/dsl")
                print("3. Paste and click 'Render'")
    else:
        if verbose:
            print("config.yaml not found")
            print("Manual upload instructions:")
            print("1. Copy the generated .dsl file content")
            print("2. Go to https://structurizr.com/dsl")
            print("3. Paste and click 'Render'")


def main():
    """Command-line interface"""
    import argparse
    
    # Set up argument parser for better CLI experience
    parser = argparse.ArgumentParser(
        description='Evaluate Python codebase and generate C4 architecture diagrams',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic evaluation
  python main.py ./my_project
  
  # With Structurizr upload via Agent
  python main.py ./my_project --upload
  
  # Quiet mode
  python main.py ./my_project --quiet
  
  # Show help for Structurizr setup
  python main.py --setup-help
"""
    )
    
    parser.add_argument(
        'codebase_path',
        nargs='?',
        help='Path to the Python codebase to evaluate'
    )
    
    parser.add_argument(
        '--upload', '-u',
        action='store_true',
        help='Upload generated DSL to Structurizr (if configured)'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output'
    )
    
    parser.add_argument(
        '--setup-help',
        action='store_true',
        help='Show Structurizr setup instructions'
    )
    
    args = parser.parse_args()
    
    # Show setup help if requested
    if args.setup_help:
        print("""
Structurizr Setup Instructions:
================================

1. Create a Structurizr account (free):
   https://structurizr.com/signup

2. Create a workspace:
   - Go to https://structurizr.com/dashboard
   - Click "Create workspace"
   - Note the workspace ID from the URL

3. Get API credentials:
   - Go to your workspace settings
   - Navigate to the API section
   - Copy API Key and API Secret

4. Add credentials to config.yaml:
   structurizr:
     api_key: "your-api-key"
     api_secret: "your-api-secret"
     workspace_id: 12345
     auto_open_browser: true

5. Run with upload:
   python main.py ./my_project --upload

Alternative (Manual Upload):
============================
If you prefer not to use the API:

   1. Run: python main.py ./my_project
   2. Open the generated .dsl file
   3. Copy the content
   4. Go to: https://structurizr.com/dsl
   5. Paste and click 'Render'

The manual method works great and doesn't require
any API setup!
""")
        sys.exit(0)
    
    # Check if codebase path was provided
    if not args.codebase_path:
        parser.print_help()
        sys.exit(1)
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: Set OPENAI_API_KEY environment variable")
        print("export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)
    
    try:
        # Run evaluation
        decision = evaluate_codebase(
            path=args.codebase_path,
            verbose=not args.quiet,
            upload_to_structurizr=args.upload
        )
        
        # Determine exit code
        success = decision and isinstance(decision, dict) and decision.get('can_use_llm')
        exit_code = 0 if success else 1
        
        if not args.quiet:
            print("\n" + "=" * 60)
            if exit_code == 0:
                print("Pipeline completed successfully!")
                if args.upload and STRUCTURIZR_AVAILABLE:
                    print("   Check your Structurizr workspace or use manual upload")
            else:
                print("Pipeline completed - codebase too complex for C4 generation")
        
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        if not args.quiet:
            import traceback
            traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()