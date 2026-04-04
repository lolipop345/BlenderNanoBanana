import sys
import base64
import threading

def run_in_thread():
    try:
        from google import genai
        from google.genai import types
        # Initialize client here
        client = genai.Client(api_key="AIzaSyA_FAKE_KEY_FOR_TESTING_123456789")
        print("SDK Initialized in thread.")
        response = client.models.generate_content(
            model="gemini-3.1-flash",
            contents="hello",
            config=types.GenerateContentConfig(temperature=0.5)
        )
        print("SDK Response finished.")
    except Exception as e:
        print(f"Exception: {e}")

t = threading.Thread(target=run_in_thread)
t.start()
t.join()
