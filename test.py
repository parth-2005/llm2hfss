# check_gemini.py
import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv()
print(f"✅ Library File: {genai.__file__}")
print(f"✅ SDK Version: {genai.__version__}")

# Check if the API Key is visible
key = os.getenv("GOOGLE_API_KEY")
if not key:
    print("❌ Error: GOOGLE_API_KEY is not set in environment variables.")
else:
    print(f"✅ API Key found: {key[:5]}... (masked)")
    
    try:
        genai.configure(api_key=key)
        models = genai.list_models()
        for model in models:
            print(f" - Model: {model.name}")
    except Exception as e:
        print(f"\n❌ API Test Failed: {e}")