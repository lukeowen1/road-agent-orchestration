"""
Agent to handle upload failures from CLI -> Structurizr Cloud.
"""

import subprocess
import shutil
import requests
from pathlib import Path
from typing import Dict, Any

class UploadFailureRecoveryAgent:
    """Diagnoses and attempts to fix upload failures"""
    
    def diagnose_and_retry(self, error_output: str, dsl_file: Path, config: Dict) -> Dict[str, Any]:
        """Main recovery method"""
        
        failure_type = self._classify_failure(error_output)
        
        print(f"Upload failed: {failure_type}")
        print("Attempting recovery...")
        
        if failure_type == "missing_cli":
            return self._handle_missing_cli(dsl_file, config)
        elif failure_type == "auth_error":
            return self._handle_auth_error(dsl_file, config)
        elif failure_type == "network_error":
            return self._handle_network_error(dsl_file, config)
        elif failure_type == "workspace_error":
            return self._handle_workspace_error(dsl_file, config)
        else:
            return self._fallback_to_manual(dsl_file)
    
    def _classify_failure(self, error_output: str) -> str:
        """Classify the type of failure from error output"""
        error_lower = error_output.lower()
        
        if any(phrase in error_lower for phrase in ["command not found", "structurizr-cli", "no such file"]):
            return "missing_cli"
        elif any(phrase in error_lower for phrase in ["unauthorized", "401", "invalid key", "authentication", "incorrect api key"]):
            return "auth_error" 
        elif any(phrase in error_lower for phrase in ["network", "timeout", "connection", "dns"]):
            return "network_error"
        elif any(phrase in error_lower for phrase in ["workspace", "403", "forbidden", "not found"]):
            return "workspace_error"
        else:
            return "unknown"
    
    def _handle_missing_cli(self, dsl_file: Path, config: Dict) -> Dict[str, Any]:
        """Handle missing Structurizr CLI"""
        
        # Try to find CLI in common locations
        possible_paths = [
            "structurizr-cli",
            "./bin/structurizr-cli", 
            "/usr/local/bin/structurizr-cli",
            shutil.which("structurizr-cli")
        ]
        
        for path in possible_paths:
            if path and shutil.which(path):
                print(f"Found CLI at: {path}")
                return self._retry_upload_with_cli(dsl_file, config, path)
        
        # CLI not found - provide installation instructions
        return {
            "recovery_successful": False,
            "error": "Structurizr CLI not found",
            "instructions": [
                "Install Structurizr CLI:",
                "1. Download from https://github.com/structurizr/cli/releases", 
                "2. Extract to a directory in your PATH",
                "3. Or specify path in config: cli_path: '/path/to/structurizr-cli'",
                "",
                "Alternative: Manual upload to https://structurizr.com/dsl"
            ]
        }
    
    def _handle_auth_error(self, dsl_file: Path, config: Dict) -> Dict[str, Any]:
        """Handle authentication errors"""
        
        structurizr_config = config.get('structurizr', {})
        workspace_id = structurizr_config.get('workspace_id')
        
        if not workspace_id:
            return {
                "recovery_successful": False,
                "error": "Missing workspace_id in config",
                "instructions": ["Add workspace_id to config.yaml under structurizr section"]
            }
        
        # Test if workspace is accessible
        workspace_url = f"https://api.structurizr.com/workspace/{workspace_id}"
        try:
            response = requests.head(workspace_url, timeout=5)
            if response.status_code == 404:
                return {
                    "recovery_successful": False,
                    "error": "Workspace not found",
                    "instructions": [
                        f"Workspace {workspace_id} does not exist or is private",
                        "Check workspace ID in config.yaml",
                        "Verify workspace exists at https://structurizr.com/workspace/{workspace_id}"
                    ]
                }
        except:
            pass
        
        return {
            "recovery_successful": False,
            "error": "Authentication failed", 
            "instructions": [
                "Check API credentials in config.yaml:",
                "1. Verify api_key and api_secret are correct",
                "2. Check workspace_id matches your workspace",
                "3. Ensure workspace allows API access",
                "",
                "Get credentials from: https://structurizr.com/workspace/{workspace_id}/settings"
            ]
        }
    
    def _handle_network_error(self, dsl_file: Path, config: Dict) -> Dict[str, Any]:
        """Handle network-related errors"""
        
        # Test basic connectivity
        try:
            response = requests.get("https://structurizr.com", timeout=5)
            if response.status_code == 200:
                print("Network seems OK, retrying upload...")
                # Retry the upload once
                from cli.upload_dsl import upload_dsl_file
                success = upload_dsl_file(str(dsl_file), config_path="config.yaml")
                
                if success:
                    return {
                        "recovery_successful": True,
                        "method": "retry_upload"
                    }
        except:
            pass
        
        return {
            "recovery_successful": False,
            "error": "Network connectivity issues",
            "instructions": [
                "Network error occurred:",
                "1. Check internet connection",
                "2. Try again in a few minutes", 
                "3. Check if corporate firewall blocks structurizr.com",
                "",
                "Alternative: Manual upload to https://structurizr.com/dsl"
            ]
        }
    
    def _handle_workspace_error(self, dsl_file: Path, config: Dict) -> Dict[str, Any]:
        """Handle workspace-related errors"""
        return {
            "recovery_successful": False,
            "error": "Workspace access error",
            "instructions": [
                "Workspace error:",
                "1. Verify workspace ID is correct",
                "2. Check workspace permissions",
                "3. Ensure workspace exists and is accessible",
                "",
                "Alternative: Create new workspace at https://structurizr.com"
            ]
        }
    
    def _retry_upload_with_cli(self, dsl_file: Path, config: Dict, cli_path: str) -> Dict[str, Any]:
        """Retry upload with specific CLI path"""
        from cli.upload_dsl import upload_dsl_with_cli
        
        structurizr_config = config.get('structurizr', {})
        
        try:
            success = upload_dsl_with_cli(
                dsl_file=str(dsl_file),
                api_key=structurizr_config.get('api_key'),
                api_secret=structurizr_config.get('api_secret'),
                workspace_id=structurizr_config.get('workspace_id'),
                cli_path=cli_path
            )
            
            return {
                "recovery_successful": success,
                "method": f"retry_with_cli_path:{cli_path}"
            }
        except Exception as e:
            return {
                "recovery_successful": False,
                "error": str(e)
            }
    
    def _fallback_to_manual(self, dsl_file: Path) -> Dict[str, Any]:
        """Fallback to manual upload instructions"""
        return {
            "recovery_successful": False,
            "error": "Could not auto-recover",
            "instructions": [
                "Manual upload required:",
                f"1. Open file: {dsl_file}",
                "2. Copy the DSL content",
                "3. Go to: https://structurizr.com/dsl",
                "4. Paste and click 'Render'"
            ]
        }