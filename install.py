import os
import sys
import json
import subprocess
import shutil

def run_cmd(cmd, check=True):
    try:
        subprocess.run(cmd, shell=True, check=check)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to run command: {cmd}\n{e}")
        return False

def main():
    print("==================================================")
    print("      MennzLore MCP Server - Auto Installer       ")
    print("==================================================")
    
    # 1. Determine repository path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(current_dir, "mcp_server", "server.py")
    
    if not os.path.exists(server_script):
        # If run from outside the repo, clone it first to a default location
        target_dir = os.path.expanduser("~/MennzLore")
        print(f"Cloning MennzLore repository to: {target_dir}")
        if os.path.exists(target_dir):
            print("Target directory already exists. Updating...")
            run_cmd(f"git -C \"{target_dir}\" pull")
        else:
            if not run_cmd(f"git clone https://github.com/mgprona/MennzLore.git \"{target_dir}\""):
                print("[ERROR] Git clone failed. Please install git or run from the cloned folder.")
                sys.exit(1)
        current_dir = target_dir
        server_script = os.path.join(current_dir, "mcp_server", "server.py")

    print(f"Using server script at: {server_script}")
    
    # 2. Install Python dependencies
    print("\nInstalling required packages (fastmcp, requests, pydantic)...")
    if not run_cmd(f"\"{sys.executable}\" -m pip install fastmcp requests pydantic"):
        print("[WARNING] Pip install returned an error. Make sure dependencies are installed.")
        
    # 3. Locate Claude Desktop config
    appdata = os.environ.get("APPDATA")
    if not appdata:
        print("[ERROR] APPDATA environment variable not found. Cannot locate Claude Desktop config.")
        sys.exit(1)
        
    claude_dir = os.path.join(appdata, "Claude")
    config_path = os.path.join(claude_dir, "claude_desktop_config.json")
    
    os.makedirs(claude_dir, exist_ok=True)
    
    # Read existing config
    config_data = {}
    if os.path.exists(config_path):
        print(f"Found existing Claude config at: {config_path}")
        # Backup config
        backup_path = config_path + ".bak"
        shutil.copyfile(config_path, backup_path)
        print(f"Created backup of your config at: {backup_path}")
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_content = f.read().strip()
                if config_content:
                    config_data = json.loads(config_content)
        except Exception as e:
            print(f"[WARNING] Could not parse existing config: {e}. Starting fresh.")
            config_data = {}

    # Initialize mcpServers structure if not present
    if "mcpServers" not in config_data:
        config_data["mcpServers"] = {}
        
    # Update config
    # Normalize paths to use forward slashes for Windows compatibility in Claude Desktop
    normalized_script_path = server_script.replace("\\", "/")
    
    config_data["mcpServers"]["mennzlore"] = {
        "command": sys.executable.replace("\\", "/"),
        "args": [normalized_script_path],
        "env": {
            "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", "YOUR_OPENROUTER_API_KEY_HERE")
        }
    }
    
    # Write back config
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        print(f"\n[SUCCESS] Claude Desktop config updated successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to write config file: {e}")
        sys.exit(1)
        
    print("\n--------------------------------------------------")
    print("Installation Complete!")
    print("1. Please RESTART your Claude Desktop application.")
    print("2. You will see a plug icon indicating the server is running.")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
