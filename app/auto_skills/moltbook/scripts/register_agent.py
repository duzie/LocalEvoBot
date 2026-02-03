from langchain_core.tools import tool
import requests
import json
from typing import Dict, Optional

API_BASE = "https://www.moltbook.com/api/v1"

@tool
def register_agent(name: str, description: str) -> Dict:
    """Register a new Moltbook AI Agent"""
    url = f"{API_BASE}/agents/register"
    headers = {"Content-Type": "application/json"}
    data = {"name": name, "description": description}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        # Save credentials to file
        if "agent" in result and "api_key" in result["agent"]:
            credentials = {
                "api_key": result["agent"]["api_key"],
                "agent_name": name
            }
            
            # Create directory if it doesn't exist
            import os
            cred_dir = os.path.expanduser("~/.config/moltbook")
            os.makedirs(cred_dir, exist_ok=True)
            
            cred_path = os.path.join(cred_dir, "credentials.json")
            with open(cred_path, "w") as f:
                json.dump(credentials, f, indent=2)
            
            result["credentials_saved_to"] = cred_path
        
        return result
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Register Moltbook agent")
    parser.add_argument("--name", required=True, help="Agent name")
    parser.add_argument("--description", required=True, help="Agent description")
    args = parser.parse_args()
    
    result = register_agent(args.name, args.description)
    print(json.dumps(result, indent=2))