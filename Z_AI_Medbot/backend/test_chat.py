# test_chat.py
import requests
import json

API = "http://127.0.0.1:5000/chat"

payload = {
    "session_id": "test-session",
    "message": "I have a mild fever and sore throat for 2 days. What should I do?"
}

resp = requests.post(API, json=payload, timeout=15)
print("status:", resp.status_code)
try:
    print(json.dumps(resp.json(), indent=2))
except Exception:
    print(resp.text)
 #End of backend/test_chat.py  