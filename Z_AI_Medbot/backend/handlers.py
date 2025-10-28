# backend/handlers.py
from .model import MedBotModel
from .utils import ocr_image_bytes, ocr_pdf_bytes
from .config import TESSERACT_CMD
from typing import Dict, Any, List
import io

# create single model instance (singleton)
MODEL = MedBotModel()

def handle_chat(session_id: str, message: str) -> Dict[str, Any]:
    # For now we ignore session_id beyond storing short-term memory in future
    reply = MODEL.generate_reply(message, session_context=[])
    return {"reply": reply}

def handle_upload(file_bytes: bytes, filename: str = "", content_type: str = "") -> Dict[str, Any]:
    # Simple detection: pdf or image
    text = ""
    try:
        if filename.lower().endswith(".pdf") or "pdf" in content_type:
            text = ocr_pdf_bytes(file_bytes)
        else:
            text = ocr_image_bytes(file_bytes)
    except Exception as e:
        text = f"[OCR error: {e}]"
    return {"extracted_text": text}
def handle_train(qa_pairs: List[Dict[str, str]]) -> Dict[str, Any]:
    MODEL.train_on_dataset(qa_pairs)
    return {"status": "trained", "new_total_pairs": len(MODEL.documents)}
def save_user_long_memory(session_id: str, summary: str, text: str) -> Dict[str, Any]:
    # Load existing long memory
    from .utils import load_json, save_json
    from .config import LONG_MEMORY_PATH

    long_mem = load_json(LONG_MEMORY_PATH, default=[]) or []
    long_mem.append({"session_id": session_id, "summary": summary, "text": text})
    save_json(LONG_MEMORY_PATH, long_mem)
    return {"status": "saved", "total_long_memory_entries": len(long_mem)}
