import sys
from google import genai
try:
    client = genai.Client(api_key="TEST", http_options={"timeout": 30.0})
    print("Client initialized")
except Exception as e:
    print(f"Error: {e}")
