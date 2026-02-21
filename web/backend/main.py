import os
import sys
import threading
import time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
if not (os.getenv("HF_ENDPOINT") or "").strip():
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
if not (os.getenv("HF_HUB_DISABLE_TELEMETRY") or "").strip():
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
if not (os.getenv("HF_HUB_DISABLE_PROGRESS_BARS") or "").strip():
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
if not (os.getenv("HF_HOME") or "").strip():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    os.environ["HF_HOME"] = os.path.join(project_root, "app", "data", "hf_cache")

from web.backend.routers import config, logs, chat, skills

app = FastAPI(title="LangChain Agent Web Console")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])

def _truthy_env(name: str, default: str = "1") -> bool:
    v = os.getenv(name)
    if v is None:
        v = default
    s = str(v).strip().lower()
    return s not in {"0", "false", "no", "off", ""}

def _prewarm_experience_store():
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if project_root not in sys.path:
            sys.path.append(project_root)
        t0 = time.time()
        from app.skills.system_skill.scripts import experience_tools
        experience_tools._init_components()
        dt_ms = int((time.time() - t0) * 1000)
        print(f"RAG warmup done ({dt_ms}ms)")
    except Exception as e:
        print(f"RAG warmup skipped: {e}")

@app.on_event("startup")
async def _startup_prewarm():
    if not _truthy_env("RAG_PREWARM_ON_STARTUP", "1"):
        return
    threading.Thread(target=_prewarm_experience_store, daemon=True).start()

# Static files (Frontend)
# Ensure the directory exists before mounting
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "web", "frontend", "public")
if not os.path.exists(frontend_path):
    os.makedirs(frontend_path)

app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")

def start():
    import uvicorn
    # Add project root to sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    if project_root not in sys.path:
        sys.path.append(project_root)
        
    port_raw = os.getenv("WEB_PORT")
    if port_raw is None or str(port_raw).strip() == "":
        port = 5010
    else:
        try:
            port = int(str(port_raw).strip())
        except Exception:
            port = 5010

    host_raw = os.getenv("WEB_HOST")
    host = (str(host_raw).strip() if host_raw is not None else "") or "0.0.0.0"
    print(f"Starting Web Console at http://{host}:{port}")
    
    # Use Config and Server to control signal handlers
    config = uvicorn.Config(app, host=host, port=port, access_log=False, log_level="warning")
    server = uvicorn.Server(config)
    
    # Disable signal handlers to allow running in a thread
    server.install_signal_handlers = lambda: None
    
    server.run()

if __name__ == "__main__":
    start()
