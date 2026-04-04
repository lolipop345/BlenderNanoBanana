import sys
from google import genai

try:
    client = genai.Client(api_key="TEST", http_options={"timeout": 120.0})
    print("SUCCESS_INIT")
except Exception as e:
    print(f"FAIL_INIT: {type(e).__name__} - {e}")
