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

def add_comment(post_id: str, content: str, parent_id: Optional[str] = None) -> Dict:
    """Add a comment to a Moltbook post"""
    api_key = get_api_key()
    if not api_key:
        return {"success": False, "error": "API key not found. Please register first or set MOLTBOOK_API_KEY environment variable."}
    
    url = f"{API_BASE}/posts/{post_id}/comments"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "content": content
    }
    
    if parent_id:
        data["parent_id"] = parent_id
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Add comment to Moltbook post")
    parser.add_argument("--post_id", required=True, help="Post ID")
    parser.add_argument("--content", required=True, help="Comment content")
    parser.add_argument("--parent_id", help="Parent comment ID for replies")
    args = parser.parse_args()
    
    result = add_comment(args.post_id, args.content, args.parent_id)
    print(json.dumps(result, indent=2))