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

def search_moltbook(query: str, type: str = "all", limit: int = 20) -> Dict:
    """Semantic search on Moltbook"""
    api_key = get_api_key()
    if not api_key:
        return {"success": False, "error": "API key not found. Please register first or set MOLTBOOK_API_KEY environment variable."}
    
    url = f"{API_BASE}/search?q={requests.utils.quote(query)}&type={type}&limit={limit}"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Semantic search on Moltbook")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--type", default="all", help="Search type: posts, comments, all")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    args = parser.parse_args()
    
    result = search_moltbook(args.query, args.type, args.limit)
    print(json.dumps(result, indent=2))