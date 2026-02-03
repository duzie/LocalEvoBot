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

def update_agent_profile(description: Optional[str] = None, metadata: Optional[Dict] = None) -> Dict:
    """Update current agent profile"""
    api_key = get_api_key()
    if not api_key:
        return {"success": False, "error": "API key not found. Please register first or set MOLTBOOK_API_KEY environment variable."}
    
    url = f"{API_BASE}/agents/me"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {}
    if description:
        data["description"] = description
    if metadata:
        data["metadata"] = metadata
    
    if not data:
        return {"success": False, "error": "No fields to update provided"}
    
    try:
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Update agent profile")
    parser.add_argument("--description", help="New profile description")
    parser.add_argument("--metadata", help="Additional metadata as JSON string")
    args = parser.parse_args()
    
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            print("Error: Invalid JSON format for metadata")
            exit(1)
    
    result = update_agent_profile(args.description, metadata)
    print(json.dumps(result, indent=2))