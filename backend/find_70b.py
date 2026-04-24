import os
from groq import Groq
from dotenv import load_dotenv

def check_70b():
    load_dotenv()
    key = os.getenv("GROQ_API_KEY", "").split(",")[0].strip()
    # Test common 70b IDs
    models_to_try = [
        "llama-3.3-70b-versatile",
        "meta-llama/llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile"
    ]
    
    client = Groq(api_key=key)
    for model in models_to_try:
        try:
            print(f"Testing {model}...")
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5
            )
            print(f"SUCCESS: {model} is available.")
            return model
        except Exception as e:
            print(f"FAILED: {model} - {e}")
    return None

if __name__ == "__main__":
    found = check_70b()
    if found:
        print(f"\nFinal Choice: {found}")
    else:
        print("\nNo 70b model found.")
