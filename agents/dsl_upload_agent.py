"""
dsl_upload_agent.py - Agent that connects DSL generation to Structurizr upload
"""
import subprocess
import sys
import time
import yaml
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
from evaluator.c4_generator import generate_c4_from_codebase
from evaluator.workflow import create_workflow
import argparse


class DSLUploadAgent:
    """Agent that monitors DSL generation and triggers upload to Structurizr"""
    
    def __init__(self, config_path: str = "config.yaml", verbose: bool = True):
        """
        Initialize the DSL upload agent
        
        Args:
            config_path: Path to configuration file
            verbose: Whether to print detailed output
        """
        self.config_path = config_path
        self.verbose = verbose
        self.upload_script = "cli/upload_dsl"  # Your upload script name
        
        # Load configuration
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load configuration from YAML file"""
        if Path(self.config_path).exists():
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        return {}
    
    def _find_latest_dsl_file(self, directory: str = ".", pattern: str = "*_c4.dsl") -> Optional[Path]:
        """
        Find the most recently created DSL file
        
        Args:
            directory: Directory to search in
            pattern: File pattern to match
            
        Returns:
            Path to the latest DSL file or None
        """
        dir_path = Path(directory)
        dsl_files = list(dir_path.glob(pattern))
        
        if not dsl_files:
            return None
        
        # Get the most recent file
        latest_file = max(dsl_files, key=lambda f: f.stat().st_mtime)
        return latest_file
    
    def _run_upload_command(self, dsl_file: Path, extra_args: list = None) -> Dict[str, Any]:
        """
        Run the upload_dsl script using subprocess
        
        Args:
            dsl_file: Path to the DSL file to upload
            extra_args: Additional arguments for the upload script
            
        Returns:
            Result dictionary with status and output
        """
        # Build command
        cmd = [sys.executable, f"{self.upload_script}.py", str(dsl_file)]
        
        # Add extra arguments if provided
        if extra_args:
            cmd.extend(extra_args)
        
        if self.verbose:
            print(f"Running upload command: {' '.join(cmd)}")
        
        try:
            # Run the upload script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Upload command timed out after 30 seconds"
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Upload script not found: {self.upload_script}.py"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def upload_dsl_file(self, dsl_file: Path, auto_open: bool = True) -> Dict[str, Any]:
        """
        Upload a specific DSL file to Structurizr
        
        Args:
            dsl_file: Path to the DSL file
            auto_open: Whether to open in browser after upload
            
        Returns:
            Result dictionary
        """
        if not dsl_file.exists():
            return {
                "success": False,
                "error": f"DSL file not found: {dsl_file}"
            }
        
        if self.verbose:
            print(f"Uploading DSL file: {dsl_file}")
            print(f"Size: {dsl_file.stat().st_size} bytes")
            print(f"Modified: {datetime.fromtimestamp(dsl_file.stat().st_mtime)}")
        
        # Prepare upload arguments
        extra_args = []
        if not auto_open:
            extra_args.append("--no-browser")
        
        # Add config file if it exists
        if Path(self.config_path).exists():
            extra_args.extend(["--config", self.config_path])
        
        # Run upload
        result = self._run_upload_command(dsl_file, extra_args)
        
        # Process result
        if result.get("success"):
            if self.verbose:
                print("Upload completed successfully!")
                if result.get("stdout"):
                    print("\nUpload output:")
                    print(result["stdout"])
        else:
            if self.verbose:
                print(f"Upload failed!")
                if result.get("error"):
                    print(f"Error: {result['error']}")
                if result.get("stderr"):
                    print(f"Details: {result['stderr']}")
        
        return result
    
    def monitor_and_upload(self, watch_directory: str = ".", check_interval: int = 2, max_wait: int = 60):
        """
        Monitor for new DSL files and upload them automatically
        
        Args:
            watch_directory: Directory to watch for DSL files
            check_interval: Seconds between checks
            max_wait: Maximum seconds to wait for a DSL file
            
        Returns:
            Result dictionary
        """
        if self.verbose:
            print(f"Monitoring for DSL files in: {watch_directory}")
            print(f"Check interval: {check_interval}s")
            print(f"Max wait: {max_wait}s")
        
        start_time = time.time()
        last_uploaded = None
        
        while (time.time() - start_time) < max_wait:
            # Find latest DSL file
            latest_dsl = self._find_latest_dsl_file(watch_directory)
            
            if latest_dsl and latest_dsl != last_uploaded:
                # New DSL file found
                if self.verbose:
                    print(f"New DSL file detected: {latest_dsl}")
                
                # Wait a moment for file to be fully written
                time.sleep(1)
                
                # Upload the file
                result = self.upload_dsl_file(latest_dsl)
                
                if result.get("success"):
                    last_uploaded = latest_dsl
                    return {
                        "success": True,
                        "uploaded_file": str(latest_dsl),
                        "result": result
                    }
                else:
                    return {
                        "success": False,
                        "attempted_file": str(latest_dsl),
                        "error": result.get("error", "Upload failed")
                    }
            
            # Wait before next check
            time.sleep(check_interval)
        
        # Timeout reached
        return {
            "success": False,
            "error": f"No DSL file found within {max_wait} seconds"
        }
    
    def process_generated_dsl(self, dsl_file_path: str, wait_for_file: bool = True) -> Dict[str, Any]:
        """
        Process a DSL file that was just generated
        
        Args:
            dsl_file_path: Path to the expected DSL file
            wait_for_file: Whether to wait for the file if it doesn't exist yet
            
        Returns:
            Result dictionary
        """
        dsl_path = Path(dsl_file_path)
        
        if wait_for_file and not dsl_path.exists():
            if self.verbose:
                print(f"Waiting for DSL file: {dsl_file_path}")
            
            # Wait up to 10 seconds for file to appear
            for _ in range(10):
                if dsl_path.exists():
                    break
                time.sleep(1)
        
        if not dsl_path.exists():
            return {
                "success": False,
                "error": f"DSL file not found after waiting: {dsl_file_path}"
            }
        
        # Upload the DSL file
        return self.upload_dsl_file(dsl_path)


class DSLUploadOrchestrator:
    """Orchestrator that connects C4 generation with Structurizr upload"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the orchestrator"""
        self.config_path = config_path
        self.agent = DSLUploadAgent(config_path)
    
    def handle_c4_generation_result(self, c4_result: Dict) -> Dict[str, Any]:
        """
        Handle the result from C4 generation and trigger upload if successful
        
        Args:
            c4_result: Result dictionary from C4 generation
            
        Returns:
            Upload result
        """
        if not c4_result.get("success"):
            return {
                "success": False,
                "error": "C4 generation was not successful",
                "c4_result": c4_result
            }
        
        # Get DSL file path
        dsl_file = c4_result.get("dsl_file")
        if not dsl_file:
            # Try to find it
            project_name = c4_result.get("project_name", "system")
            expected_file = f"{project_name.lower().replace(' ', '_')}_c4.dsl"
            dsl_file = expected_file
        
        # Upload the DSL
        print("\n" + "="*60)
        print("DSL Upload Agent Active")
        print("="*60)
        
        upload_result = self.agent.process_generated_dsl(dsl_file)
        
        return {
            "c4_generation": c4_result,
            "upload": upload_result,
            "overall_success": upload_result.get("success", False)
        }
    
    def run_complete_flow(self, codebase_path: str, project_name: Optional[str] = None) -> Dict:
        """
        Run the complete flow: evaluate → generate C4 → upload to Structurizr
        
        Args:
            codebase_path: Path to the codebase
            project_name: Optional project name
            
        Returns:
            Complete result dictionary
        """
        
        # Step 1: Evaluate codebase
        print("Step 1: Evaluating codebase...")
        workflow = create_workflow()
        
        initial_state = {
            "codebase_path": str(Path(codebase_path).absolute()),
            "analysis": {},
            "decision": {},
            "summary": "",
            "config_path": self.config_path
        }
        
        eval_result = workflow.invoke(initial_state)
        decision = eval_result.get('decision', {})
        
        if not decision.get('can_use_llm'):
            return {
                "success": False,
                "error": "Codebase too complex for C4 generation",
                "evaluation": eval_result
            }
        
        # Step 2: Generate C4
        print("\nStep 2: Generating C4 DSL...")
        c4_result = generate_c4_from_codebase(
            codebase_path=codebase_path,
            decision=decision,
            project_name=project_name or Path(codebase_path).name,
            config_path=self.config_path,
            save_dsl=True
        )
        
        # Step 3: Upload to Structurizr
        print("\nStep 3: Uploading to Structurizr...")
        upload_result = self.handle_c4_generation_result(c4_result)
        
        return {
            "evaluation": eval_result,
            "c4_generation": c4_result,
            "upload": upload_result.get("upload"),
            "success": upload_result.get("overall_success", False)
        }


def main():
    """CLI for the DSL upload agent"""  
    parser = argparse.ArgumentParser(
        description='DSL Upload Agent - Automatically upload generated DSL to Structurizr',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload a specific DSL file
  python dsl_upload_agent.py upload ./my_system_c4.dsl
  
  # Monitor directory for new DSL files
  python dsl_upload_agent.py monitor ./output_directory
  
  # Run complete flow
  python dsl_upload_agent.py complete ./my_codebase
  
  # Process result from C4 generation
  python dsl_upload_agent.py process --dsl-file ./system_c4.dsl
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload a specific DSL file')
    upload_parser.add_argument('dsl_file', help='Path to DSL file')
    upload_parser.add_argument('--no-browser', action='store_true', help='Do not open browser')
    
    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor for new DSL files')
    monitor_parser.add_argument('directory', nargs='?', default='.', help='Directory to monitor')
    monitor_parser.add_argument('--interval', type=int, default=2, help='Check interval in seconds')
    monitor_parser.add_argument('--timeout', type=int, default=60, help='Maximum wait time in seconds')
    
    # Complete flow command
    complete_parser = subparsers.add_parser('complete', help='Run complete flow')
    complete_parser.add_argument('codebase', help='Path to codebase')
    complete_parser.add_argument('--name', help='Project name')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process generated DSL')
    process_parser.add_argument('--dsl-file', required=True, help='Expected DSL file path')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize agent
    agent = DSLUploadAgent()
    
    try:
        if args.command == 'upload':
            # Upload specific file
            result = agent.upload_dsl_file(
                Path(args.dsl_file),
                auto_open=not args.no_browser
            )
            sys.exit(0 if result.get("success") else 1)
            
        elif args.command == 'monitor':
            # Monitor for new files
            result = agent.monitor_and_upload(
                watch_directory=args.directory,
                check_interval=args.interval,
                max_wait=args.timeout
            )
            sys.exit(0 if result.get("success") else 1)
            
        elif args.command == 'complete':
            # Run complete flow
            orchestrator = DSLUploadOrchestrator()
            result = orchestrator.run_complete_flow(
                codebase_path=args.codebase,
                project_name=args.name
            )
            
            if result.get("success"):
                print("Complete pipeline successful!")
            else:
                print(f"Pipeline failed: {result.get('error', 'Unknown error')}")
            
            sys.exit(0 if result.get("success") else 1)
            
        elif args.command == 'process':
            # Process generated DSL
            result = agent.process_generated_dsl(args.dsl_file)
            sys.exit(0 if result.get("success") else 1)
            
    except KeyboardInterrupt:
        print("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()