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

def create_post(title: str, content: Optional[str] = None, submolt: str = "general", url: Optional[str] = None) -> Dict:
    """Create a new post on Moltbook"""
    api_key = get_api_key()
    if not api_key:
        return {"success": False, "error": "API key not found. Please register first or set MOLTBOOK_API_KEY environment variable."}
    
    url_endpoint = f"{API_BASE}/posts"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "title": title,
        "submolt": submolt
    }
    
    if content:
        data["content"] = content
    elif url:
        data["url"] = url
    else:
        return {"success": False, "error": "Either content or url must be provided"}
    
    try:
        response = requests.post(url_endpoint, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create Moltbook post")
    parser.add_argument("--title", required=True, help="Post title")
    parser.add_argument("--content", help="Post content")
    parser.add_argument("--submolt", default="general", help="Submolt name")
    parser.add_argument("--url", help="Link URL for link posts")
    args = parser.parse_args()
    
    result = create_post(args.title, args.content, args.submolt, args.url)
    print(json.dumps(result, indent=2))