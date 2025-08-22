"""
structurizr_client.py - Client for interacting with Structurizr API
"""
import base64
import hashlib
import hmac
import json
import requests
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse


class StructurizrClient:
    """Client for Structurizr API interactions"""
    
    def __init__(self, api_key: str = None, api_secret: str = None, workspace_id: int = None, config_path: str = "config.yaml"):
        """
        Initialize Structurizr client
        
        Args:
            api_key: Structurizr API key
            api_secret: Structurizr API secret
            workspace_id: Workspace ID to use
            config_path: Path to configuration file
        """
        # Load from config if not provided
        if not all([api_key, api_secret, workspace_id]):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                structurizr_config = config.get('structurizr', {})
                
                api_key = api_key or structurizr_config.get('api_key')
                api_secret = api_secret or structurizr_config.get('api_secret')
                workspace_id = workspace_id or structurizr_config.get('workspace_id')
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.workspace_id = workspace_id
        self.base_url = "https://api.structurizr.com"
        
        # Validate credentials
        if not all([self.api_key, self.api_secret, self.workspace_id]):
            raise ValueError("Missing Structurizr credentials. Set api_key, api_secret, and workspace_id")
    
    def _generate_signature(self, method: str, path: str, content: str = "", content_type: str = "", nonce: str = "") -> str:
        """
        Generate HMAC signature for API authentication
        
        Args:
            method: HTTP method (GET, PUT, etc.)
            path: API path
            content: Request body content
            content_type: Content-Type header value
            nonce: Unique nonce for request
            
        Returns:
            Base64 encoded signature
        """
        # Calculate content MD5
        if content:
            content_md5 = base64.b64encode(
                hashlib.md5(content.encode('utf-8')).digest()
            ).decode('utf-8')
        else:
            content_md5 = ""
        
        # Build string to sign
        string_to_sign = "\n".join([
            method.upper(),
            path,
            content_md5,
            content_type,
            nonce
        ])
        
        # Generate HMAC
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _make_request(self, method: str, path: str, data: Dict = None) -> requests.Response:
        """
        Make authenticated request to Structurizr API
        
        Args:
            method: HTTP method
            path: API path
            data: Request data
            
        Returns:
            Response object
        """
        url = f"{self.base_url}{path}"
        
        # Prepare content
        content = json.dumps(data) if data else ""
        content_type = "application/json; charset=UTF-8" if data else ""
        
        # Generate nonce (timestamp)
        nonce = str(int(datetime.now().timestamp() * 1000))
        
        # Generate signature
        signature = self._generate_signature(method, path, content, content_type, nonce)
        
        # Build headers
        headers = {
            "X-Authorization": f"{self.api_key}:{signature}",
            "Nonce": nonce,
            "User-Agent": "structurizr-python/1.0"
        }
        
        if content_type:
            headers["Content-Type"] = content_type
        
        # Make request
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=content
        )
        
        return response
    
    def get_workspace(self) -> Dict:
        """
        Get workspace details
        
        Returns:
            Workspace data
        """
        path = f"/workspace/{self.workspace_id}"
        response = self._make_request("GET", path)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get workspace: {response.status_code} - {response.text}")
    
    def upload_workspace(self, workspace_json: Dict) -> Dict:
        """
        Upload workspace JSON to Structurizr
        
        Args:
            workspace_json: Workspace in JSON format
            
        Returns:
            Response data
        """
        path = f"/workspace/{self.workspace_id}"
        response = self._make_request("PUT", path, workspace_json)
        
        if response.status_code in [200, 204]:
            return {"success": True, "message": "Workspace uploaded successfully"}
        else:
            raise Exception(f"Failed to upload workspace: {response.status_code} - {response.text}")
    
    def lock_workspace(self) -> Dict:
        """Lock the workspace to prevent concurrent modifications"""
        path = f"/workspace/{self.workspace_id}/lock"
        response = self._make_request("PUT", path)
        
        if response.status_code in [200, 204]:
            return {"success": True, "locked": True}
        else:
            raise Exception(f"Failed to lock workspace: {response.status_code}")
    
    def unlock_workspace(self) -> Dict:
        """Unlock the workspace"""
        path = f"/workspace/{self.workspace_id}/lock"
        response = self._make_request("DELETE", path)
        
        if response.status_code in [200, 204]:
            return {"success": True, "locked": False}
        else:
            raise Exception(f"Failed to unlock workspace: {response.status_code}")


class DSLToStructurizr:
    """Convert DSL to Structurizr JSON and upload"""
    
    def __init__(self, client: StructurizrClient):
        """
        Initialize with Structurizr client
        
        Args:
            client: StructurizrClient instance
        """
        self.client = client
    
    def convert_dsl_to_json(self, dsl: str) -> Dict:
        """
        Convert DSL to Structurizr JSON format
        
        Note: This is a simplified conversion. For production use,
        you might want to use the official Structurizr CLI or
        a more complete DSL parser.
        
        Args:
            dsl: Structurizr DSL content
            
        Returns:
            JSON representation
        """
        # For now, we'll need to use the Structurizr CLI or online converter
        # This is a placeholder that creates a basic structure
        
        # Extract workspace name from DSL
        import re
        workspace_match = re.search(r'workspace\s+"([^"]+)"', dsl)
        name = workspace_match.group(1) if workspace_match else "System"
        
        # Basic workspace structure
        workspace_json = {
            "id": self.client.workspace_id,
            "name": name,
            "description": "Generated from DSL",
            "model": {
                "people": [],
                "softwareSystems": []
            },
            "views": {
                "systemContextViews": [],
                "containerViews": [],
                "componentViews": []
            },
            "documentation": {}
        }
        
        return workspace_json
    
    def upload_dsl(self, dsl: str, convert_online: bool = True) -> Dict:
        """
        Upload DSL to Structurizr
        
        Args:
            dsl: Structurizr DSL content
            convert_online: Whether to use online conversion (recommended)
            
        Returns:
            Upload result
        """
        if convert_online:
            # Direct DSL upload endpoint (if available)
            # Note: This requires Structurizr to support DSL upload
            return self._upload_dsl_directly(dsl)
        else:
            # Convert to JSON first (limited functionality)
            workspace_json = self.convert_dsl_to_json(dsl)
            return self.client.upload_workspace(workspace_json)
    
    def _upload_dsl_directly(self, dsl: str) -> Dict:
        """
        Upload DSL directly using workspace update
        
        Note: The best approach is to use Structurizr CLI or
        the online DSL editor for conversion
        """
        # For direct DSL upload, you typically need to:
        # 1. Use Structurizr CLI to convert DSL to JSON
        # 2. Upload the JSON
        
        instructions = {
            "success": False,
            "message": "Direct DSL upload requires Structurizr CLI",
            "instructions": [
                "1. Save DSL to file: workspace.dsl",
                "2. Use Structurizr CLI: structurizr push -w workspace.dsl",
                "3. Or use online editor: https://structurizr.com/dsl",
                f"4. Your workspace URL: https://structurizr.com/workspace/{self.client.workspace_id}"
            ],
            "workspace_url": f"https://structurizr.com/workspace/{self.client.workspace_id}",
            "dsl_editor_url": "https://structurizr.com/dsl"
        }
        
        return instructions


class StructurizrVisualizer:
    """Handle visualization of Structurizr diagrams"""
    
    def __init__(self, workspace_id: int, config_path: str = "config.yaml"):
        """
        Initialize visualizer
        
        Args:
            workspace_id: Structurizr workspace ID
            config_path: Path to configuration
        """
        self.workspace_id = workspace_id
        
        # Load config for additional settings
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
    
    def get_diagram_urls(self) -> Dict[str, str]:
        """
        Get URLs for various diagram views
        
        Returns:
            Dictionary of diagram URLs
        """
        base_url = f"https://structurizr.com/workspace/{self.workspace_id}"
        
        urls = {
            "workspace": base_url,
            "diagrams": f"{base_url}/diagrams",
            "system_context": f"{base_url}/diagrams#SystemContext",
            "container": f"{base_url}/diagrams#Container",
            "component": f"{base_url}/diagrams#Component",
            "explore": f"{base_url}/explore",
            "documentation": f"{base_url}/documentation",
            "decisions": f"{base_url}/decisions"
        }
        
        return urls
    
    def open_in_browser(self, view: str = "diagrams"):
        """
        Open Structurizr workspace in browser
        
        Args:
            view: Which view to open (diagrams, explore, etc.)
        """
        import webbrowser
        
        urls = self.get_diagram_urls()
        url = urls.get(view, urls["workspace"])
        
        print(f"Opening Structurizr workspace in browser...")
        print(f"URL: {url}")
        
        webbrowser.open(url)
    
    def generate_export_urls(self) -> Dict[str, str]:
        """
        Generate URLs for exporting diagrams
        
        Returns:
            Dictionary of export URLs
        """
        base_url = f"https://structurizr.com/workspace/{self.workspace_id}"
        
        exports = {
            "png": f"{base_url}/images",
            "svg": f"{base_url}/images?format=svg", 
            "plantuml": f"{base_url}/plantuml",
            "mermaid": f"{base_url}/mermaid",
            "json": f"{base_url}/json"
        }
        
        return exports


def upload_dsl_to_structurizr(
    dsl_content: str,
    api_key: str = None,
    api_secret: str = None,
    workspace_id: int = None,
    config_path: str = "config.yaml",
    open_browser: bool = True
) -> Dict:
    """
    Main function to upload DSL to Structurizr and visualize
    
    Args:
        dsl_content: The DSL content to upload
        api_key: Structurizr API key
        api_secret: Structurizr API secret
        workspace_id: Workspace ID
        config_path: Path to configuration
        open_browser: Whether to open the result in browser
        
    Returns:
        Result dictionary with URLs and status
    """
    try:
        # Initialize client
        client = StructurizrClient(api_key, api_secret, workspace_id, config_path)
        
        # Initialize DSL uploader
        uploader = DSLToStructurizr(client)
        
        # Upload DSL (will provide instructions for now)
        upload_result = uploader.upload_dsl(dsl_content)
        
        # Initialize visualizer
        visualizer = StructurizrVisualizer(workspace_id, config_path)
        
        # Get URLs
        urls = visualizer.get_diagram_urls()
        export_urls = visualizer.generate_export_urls()
        
        # Open in browser if requested
        if open_browser and upload_result.get("success"):
            visualizer.open_in_browser()
        
        # Prepare result
        result = {
            "upload_status": upload_result,
            "workspace_id": workspace_id,
            "urls": urls,
            "export_urls": export_urls,
            "instructions": upload_result.get("instructions", [])
        }
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to upload to Structurizr"
        }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python structurizr_client.py <dsl_file>")
        sys.exit(1)
    
    # Read DSL file
    dsl_file = sys.argv[1]
    with open(dsl_file, 'r') as f:
        dsl_content = f.read()
    
    # Upload and visualize
    result = upload_dsl_to_structurizr(dsl_content)
    
    if result.get("upload_status", {}).get("success"):
        print("Upload successful!")
        print(f"View at: {result['urls']['workspace']}")
    else:
        print("Instructions for uploading DSL:")
        for instruction in result.get("instructions", []):
            print(f"{instruction}")