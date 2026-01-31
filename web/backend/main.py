import os
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from web.backend.routers import config, logs, chat

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
        
    port = int(os.getenv("WEB_PORT", 5010))
    host = os.getenv("WEB_HOST", "0.0.0.0")
    print(f"Starting Web Console at http://{host}:{port}")
    
    # Use Config and Server to control signal handlers
    config = uvicorn.Config(app, host=host, port=port, access_log=False, log_level="warning")
    server = uvicorn.Server(config)
    
    # Disable signal handlers to allow running in a thread
    server.install_signal_handlers = lambda: None
    
    server.run()

if __name__ == "__main__":
    start()
