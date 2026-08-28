"""
PRO-VERSED — Root Deployment & Execution Entrypoint
Seamlessly bridges root and subfolder execution for any cloud host (Render, Railway, Fly.io, Heroku, Local).
"""
import os
import sys

root_dir = os.path.dirname(os.path.abspath(__file__))
pv_dir = os.path.join(root_dir, "Pro-Versed")
backend_dir = os.path.join(pv_dir, "backend")

for p in [backend_dir, pv_dir]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    from backend.main import app
except ImportError:
    import main
    app = main.app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting PRO-VERSED on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=False)
