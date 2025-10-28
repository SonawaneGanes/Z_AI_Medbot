# backend/interface.py
"""
FastAPI routes - main interface used by frontend.
"""
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    result = handle_chat(req.session_id, req.message)
    return result

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    res = handle_upload(content, filename=file.filename, content_type=file.content_type or "")
    return res

# simple sample route
@app.get("/sample_training_format")
def sample_training_format():
    return {
        "example": [
            {"question": "What are symptoms of diabetes?", "answer": "Common symptoms include increased thirst, frequent urination, fatigue."}
        ]
    }

if __name__ == "__main__":
    # Run with module style so `python -m backend.interface` works from project root
    uvicorn.run("backend.interface:app", host="127.0.0.1", port=5000, reload=True)
# --- IGNORE ---