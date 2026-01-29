from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import dotenv_values, set_key
import os

router = APIRouter()

class ConfigUpdate(BaseModel):
    key: str
    value: str

@router.get("")
async def get_config():
    """Get all environment variables from .env file"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    env_path = os.path.join(base_dir, ".env")
    if not os.path.exists(env_path):
        return {}
    return dotenv_values(env_path)

@router.post("")
async def update_config(config: ConfigUpdate):
    """Update a specific environment variable"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    env_path = os.path.join(base_dir, ".env")

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                f.write("")
        
        set_key(env_path, config.key, config.value)
        os.environ[config.key] = config.value
        return {"status": "success", "key": config.key, "value": config.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
