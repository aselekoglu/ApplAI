import os
from dotenv import load_dotenv
import google.generativeai as genai

def test():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is missing.")
        return
        
    genai.configure(api_key=api_key)
    print("Listing available models for this API key:")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test()
