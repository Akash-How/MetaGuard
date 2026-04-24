import os
from groq import Groq
from dotenv import load_dotenv

def test_groq_keys():
    load_dotenv()
    api_key_str = os.getenv("GROQ_API_KEY", "")
    model = os.getenv("GROQ_MODEL_DEFAULT", "meta-llama/llama-4-scout-17b-16e-instruct")
    
    if not api_key_str:
        print("❌ No GROQ_API_KEY found in .env")
        return

    keys = [k.strip() for k in api_key_str.split(",") if k.strip()]
    print(f"Found {len(keys)} keys. Testing connectivity and rate limits...\n")

    for i, key in enumerate(keys):
        print(f"--- Key {i} ({key[:10]}...) ---")
        try:
            client = Groq(api_key=key)
            # Minimal request to test validity and model access
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Keep it short: Hello!"}],
                max_tokens=5
            )
            print("Status: VALID")
            print(f"Response: {response.choices[0].message.content}")
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "rate_limit" in err_msg:
                print("Status: RATE LIMITED (429)")
                print(f"📝 Details: {err_msg[:200]}...")
            elif "401" in err_msg or "api_key" in err_msg:
                print("Status: INVALID KEY (401)")
            elif "404" in err_msg or "model_not_found" in err_msg:
                print(f"Status: MODEL NOT FOUND (404) - check '{model}' access")
            else:
                print(f"Status: UNKNOWN ERROR")
                print(f"📝 Details: {err_msg}")
        print("\n")

if __name__ == "__main__":
    test_groq_keys()
