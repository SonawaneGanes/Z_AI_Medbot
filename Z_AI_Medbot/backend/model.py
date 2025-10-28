# backend/model.py
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import pickle
import numpy as np
import json
import os

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import DATASETS_DIR, TFIDF_MAX_FEATURES, VECTOR_STORE_PATH, TOP_K_RETRIEVAL, OPENAI_API_KEY
from .utils import load_json, save_json
from .config import SAMPLE_DATASET, LONG_MEMORY_PATH
from .prompts import DISCLAIMER, SYSTEM_PROMPT

# Optional OpenAI import - only required if user has key
try:
    import openai
    if OPENAI_API_KEY:
        openai.api_key = OPENAI_API_KEY
except Exception:
    openai = None

class MedBotModel:
    def __init__(self):
        self.dataset_path = SAMPLE_DATASET
        self.qa_pairs: List[Dict] = []
        self.documents: List[Dict] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.doc_vectors = None
        self._ensure_sample_dataset()
        self._load_dataset()
        self._build_vector_store()

    def _ensure_sample_dataset(self):
        # write a sample dataset if none exists (helps first run)
        if not self.dataset_path.exists():
            sample = [
                {"question": "What are common causes of a headache?", "answer": "Stress, dehydration, poor sleep; if severe or sudden get medical help."},
                {"question": "What is hypertension?", "answer": "High blood pressure; lifestyle and medications are common controls."},
                {"question": "How to manage fever at home?", "answer": "Stay hydrated, rest, use fever reducers per local guidelines."}
            ]
            save_json(self.dataset_path, sample)

    def _load_dataset(self):
        data = load_json(self.dataset_path, default=[])
        self.qa_pairs = data or []

    def _augment_with_long_memory(self) -> List[Dict]:
        mem = load_json(LONG_MEMORY_PATH, default=[]) or []
        docs = []
        for idx, entry in enumerate(mem):
            docs.append({"id": f"mem-{idx}", "question": entry.get("summary", "") or entry.get("text", ""), "answer": entry.get("text", "")})
        return docs

    def _build_vector_store(self):
        # Build combined documents list
        docs = []
        for idx, qa in enumerate(self.qa_pairs):
            q = qa.get("question", "").strip()
            a = qa.get("answer", "").strip()
            if q:
                docs.append({"id": f"qa-{idx}", "question": q, "answer": a})
        docs.extend(self._augment_with_long_memory())
        self.documents = docs

        texts = [d["question"] for d in docs if d.get("question")]
        if not texts:
            # Guard: no texts to vectorize
            self.vectorizer = None
            self.doc_vectors = None
            return

        try:
            self.vectorizer = TfidfVectorizer(max_features=TFIDF_MAX_FEATURES).fit(texts)
            self.doc_vectors = self.vectorizer.transform(texts)
            # persist vectorizer and docs
            with open(VECTOR_STORE_PATH, "wb") as f:
                pickle.dump({"documents": self.documents, "vectorizer": self.vectorizer, "doc_vectors": self.doc_vectors}, f)
        except ValueError as e:
            # empty vocabulary / stopwords-only; clear vector store safely
            self.vectorizer = None
            self.doc_vectors = None

    def reload_vector_store(self):
        try:
            with open(VECTOR_STORE_PATH, "rb") as f:
                data = pickle.load(f)
                self.documents = data["documents"]
                self.vectorizer = data["vectorizer"]
                self.doc_vectors = data["doc_vectors"]
        except Exception:
            self._build_vector_store()

    def retrieve_similar(self, query: str, top_k: int = TOP_K_RETRIEVAL) -> List[Tuple[Dict, float]]:
        q = (query or "").strip()
        if not q or not self.vectorizer or self.doc_vectors is None:
            return []
        q_vec = self.vectorizer.transform([q])
        sims = cosine_similarity(q_vec, self.doc_vectors).flatten()
        idxs = np.argsort(-sims)[:top_k]
        results = []
        for i in idxs:
            results.append((self.documents[i], float(sims[i])))
        return results

    def _explain_medical_terms(self, text: str) -> str:
        # naive mapping for demo – extend as needed
        mappings = {
            "hypertension": "high blood pressure",
            "tachycardia": "fast heart rate",
            "bradycardia": "slow heart rate",
            "cbc": "complete blood count"
        }
        found = []
        t = text.lower()
        for k, v in mappings.items():
            if k in t:
                found.append(f"{k}: {v}")
        return " | ".join(found)

    def _precautionary_advice(self, text: str) -> str:
        t = text.lower()
        adv = []
        if "fever" in t: adv.append("hydrate, rest, monitor temperature.")
        if "cough" in t: adv.append("stay hydrated, avoid smoke; see provider if severe.")
        if not adv: adv.append("track symptoms, rest, seek care if worsening.")
        return " ".join(adv)

    def _when_to_see_doctor(self, text: str) -> str:
        t = text.lower()
        if any(x in t for x in ["chest pain", "shortness of breath", "unconscious", "severe"]):
            return "Seek emergency care immediately."
        return "Consult a healthcare provider if symptoms worsen or persist."

    def generate_reply(self, user_text: str, session_context: List[Dict] = None) -> str:
        user_text = (user_text or "").strip()
        # Safety: refuse diagnosis/prescriptions
        lower = user_text.lower()
        banned = ["diagnose", "diagnosis", "prescribe", "prescription", "what medicine", "what drug"]
        if any(b in lower for b in banned):
            return ("I cannot provide diagnoses or prescriptions. Please consult a medical professional.\n\n" + DISCLAIMER)

        # Try retrieval
        retrieved = self.retrieve_similar(user_text, top_k=3)
        reply_parts = []
        highest_score = 0.0
        if retrieved:
            for doc, score in retrieved:
                if score > 0.05:
                    reply_parts.append(f"Related: {doc.get('answer')}")
                if score > highest_score:
                    highest_score = score

        if not reply_parts:
            reply_parts.append("I have limited matched content. Here are general suggestions:")

        expl = self._explain_medical_terms(user_text)
        if expl:
            reply_parts.append("Simplified terms: " + expl)

        reply_parts.append("Advice: " + self._precautionary_advice(user_text))
        reply_parts.append("When to see a doctor: " + self._when_to_see_doctor(user_text))

        composed = "\n\n".join(reply_parts) + "\n\n" + DISCLAIMER

        # If retrieval confidence low and OpenAI available, call OpenAI for a better response
        if highest_score < 0.12 and openai and OPENAI_API_KEY:
            try:
                prompt = f"{SYSTEM_PROMPT}\nUser: {user_text}\n\nProvide an educational (non-diagnostic) response, keep it concise and include a disclaimer."
                resp = openai.ChatCompletion.create(
                    model="gpt-4o-mini",  # use a safe default; change as needed
                    messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":user_text}],
                    max_tokens=400,
                    temperature=0.2
                )
                oa = resp.choices[0].message.content.strip()
                return oa + "\n\n" + DISCLAIMER
            except Exception:
                # If OpenAI fails, fallback to composed
                return composed
        else:
            return composed

    def train_on_dataset(self, new_pairs: List[Dict]):
        data = load_json(self.dataset_path, default=[]) or []
        data.extend(new_pairs)
        save_json(self.dataset_path, data)
        self._load_dataset()
        self._build_vector_store()
MODEL = MedBotModel()