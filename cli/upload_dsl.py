"""
upload_dsl.py - Simple CLI tool to upload DSL files to Structurizr using the Structurizr CLI
"""
import sys
import os
import yaml
import webbrowser
import subprocess
from pathlib import Path
from typing import Optional


def upload_dsl_with_cli(
    dsl_file: str,
    api_key: str,
    api_secret: str,
    workspace_id: int,
    cli_path: str = "structurizr-cli",
    open_browser: bool = True
) -> bool:
    """
    Upload DSL to Structurizr Cloud using the Structurizr CLI.
    """
    if not Path(dsl_file).exists():
        print(f"Error: DSL file not found: {dsl_file}")
        return False

    cmd = [
        cli_path, "push",
        "-id", str(workspace_id),
        "-key", api_key,
        "-secret", api_secret,
        "-w", dsl_file
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode == 0:
        print("Upload successful!")
        workspace_url = f"https://structurizr.com/workspace/{workspace_id}"
        print(f"View at: {workspace_url}")
        if open_browser:
            webbrowser.open(workspace_url)
        return True
    else:
        print("Upload failed!")
        print(result.stderr)
        return False


def upload_dsl_file(
    dsl_file: str,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    workspace_id: Optional[int] = None,
    config_path: str = "config.yaml",
    open_browser: bool = True
):
    """
    Upload a DSL file to Structurizr using the CLI, or provide manual instructions.
    """
    # Read DSL file
    if not Path(dsl_file).exists():
        print(f"Error: DSL file not found: {dsl_file}")
        return False

    with open(dsl_file, 'r') as f:
        dsl_content = f.read()

    print(f"Read DSL from: {dsl_file}")
    print(f"Size: {len(dsl_content)} characters")

    # Load config if credentials not provided
    if not all([api_key, api_secret, workspace_id]):
        if Path(config_path).exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                structurizr_config = config.get('structurizr', {})
                api_key = api_key or structurizr_config.get('api_key')
                api_secret = api_secret or structurizr_config.get('api_secret')
                workspace_id = workspace_id or structurizr_config.get('workspace_id')

    # Check if we have credentials
    if all([api_key, api_secret, workspace_id]):
        return upload_dsl_with_cli(
            dsl_file=dsl_file,
            api_key=api_key,
            api_secret=api_secret,
            workspace_id=workspace_id,
            open_browser=open_browser
        )
    else:
        print("Structurizr API credentials not configured")
        print("Option 1: Manual Upload")
        print("=" * 40)
        print("1. Copy your DSL content")
        print("2. Go to: https://structurizr.com/dsl")
        print("3. Paste and click 'Render'")

        if open_browser:
            response = input("\nOpen Structurizr DSL editor in browser? (y/n): ")
            if response.lower() == 'y':
                webbrowser.open("https://structurizr.com/dsl")

        print("Option 2: Configure API")
        print("=" * 40)
        print("1. Get credentials from https://structurizr.com/help/web-api")
        print("2. Add to config.yaml or use command line arguments:")
        print("python upload_dsl.py file.dsl --api-key KEY --api-secret SECRET --workspace-id ID")

        return False


def main():
    """Main CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Upload Structurizr DSL files using the Structurizr CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload using config.yaml
  python upload_dsl.py my_system_c4.dsl

  # Upload with explicit credentials
  python upload_dsl.py my_system_c4.dsl --api-key KEY --api-secret SECRET --workspace-id 12345
"""
    )

    parser.add_argument(
        'dsl_file',
        help='Path to DSL file'
    )
    parser.add_argument(
        '--api-key',
        help='Structurizr API key'
    )
    parser.add_argument(
        '--api-secret',
        help='Structurizr API secret'
    )
    parser.add_argument(
        '--workspace-id',
        type=int,
        help='Structurizr workspace ID'
    )
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Configuration file (default: config.yaml)'
    )
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not open browser after upload'
    )

    args = parser.parse_args()

    success = upload_dsl_file(
        dsl_file=args.dsl_file,
        api_key=args.api_key,
        api_secret=args.api_secret,
        workspace_id=args.workspace_id,
        config_path=args.config,
        open_browser=not args.no_browser
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()