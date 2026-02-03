from langchain_core.tools import tool
import requests
import json
import os
from typing import Dict, Optional

API_BASE = "https://www.moltbook.com/api/v1"

@tool
def get_api_key() -> Optional[str]:
    """Get API key from credentials file or environment variable"""
    # Try environment variable first
    api_key = os.environ.get("MOLTBOOK_API_KEY")
    if api_key:
        return api_key
    
    # Try credentials file
    cred_path = os.path.expanduser("~/.config/moltbook/credentials.json")
    if os.path.exists(cred_path):
        with open(cred_path, "r") as f:
            credentials = json.load(f)
            return credentials.get("api_key")
    
    return None

def get_agent_profile(agent_name: Optional[str] = None) -> Dict:
    """Get agent profile"""
    api_key = get_api_key()
    if not api_key:
        return {"success": False, "error": "API key not found. Please register first or set MOLTBOOK_API_KEY environment variable."}
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    if agent_name:
        url = f"{API_BASE}/agents/profile?name={requests.utils.quote(agent_name)}"
    else:
        url = f"{API_BASE}/agents/me"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Get agent profile")
    parser.add_argument("--agent_name", help="Agent name (leave empty for own profile)")
    args = parser.parse_args()
    
    result = get_agent_profile(args.agent_name)
    print(json.dumps(result, indent=2))