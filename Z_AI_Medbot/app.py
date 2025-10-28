from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import sys, os
from pathlib import Path

# Add backend path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from handlers import handle_chat, handle_upload, handle_train, save_user_long_memory

# --- FastAPI setup ---
app = FastAPI()

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Frontend paths ---
BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"

# Serve static files (CSS, JS)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Serve index.html
@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")

# Optional favicon
@app.get("/favicon.ico")
async def favicon():
    path = FRONTEND_DIR / "favicon.ico"
    if path.exists():
        return FileResponse(path)
    return {"error": "favicon not found"}

# --- API endpoints ---
class ChatRequest(BaseModel):
    message: str

@app.get("/ping")
async def ping():
    return {"status": "ok"}

@app.post("/chat")
async def chat(req: ChatRequest):
    return await handle_chat(req.message)

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    return await handle_upload(file)

@app.post("/train")
async def train(data: str = Form(...)):
    return await handle_train(data)

# --- Run app ---
if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)
