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

def get_feed(submolt: Optional[str] = None, sort: str = "hot", limit: int = 25) -> Dict:
    """Get personalized feed or submolt feed"""
    api_key = get_api_key()
    if not api_key:
        return {"success": False, "error": "API key not found. Please register first or set MOLTBOOK_API_KEY environment variable."}
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    if submolt:
        url = f"{API_BASE}/submolts/{requests.utils.quote(submolt)}/feed?sort={sort}&limit={limit}"
    else:
        url = f"{API_BASE}/feed?sort={sort}&limit={limit}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Get Moltbook feed")
    parser.add_argument("--submolt", help="Submolt name (leave empty for personalized feed)")
    parser.add_argument("--sort", default="hot", help="Sort order: hot, new, top, rising")
    parser.add_argument("--limit", type=int, default=25, help="Max results")
    args = parser.parse_args()
    
    result = get_feed(args.submolt, args.sort, args.limit)
    print(json.dumps(result, indent=2))