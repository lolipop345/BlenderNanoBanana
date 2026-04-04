import sys
import threading
from google import genai
from google.genai import types

def run():
    print("Testing genai in thread...")
    with open('/Users/memed/Documents/BlenderNanoBanana/blender_addon/preferences.py', 'r') as f:
        # just try to load google.genai
        pass

    print("Importing successful...")
    # wait I need the api key to actually test
