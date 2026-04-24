import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.config import get_settings

def verify_groq_keys():
    settings = get_settings()
    keys = settings.groq_api_key_list
    print(f"Number of Groq keys detected: {len(keys)}")
    for i, key in enumerate(keys):
        print(f"Key {i+1}: {key[:10]}...{key[-5:]}")
    
    expected_count = 3
    if len(keys) == expected_count:
        print("SUCCESS: 3 keys correctly parsed.")
    else:
        print(f"FAILURE: Expected {expected_count} keys, but found {len(keys)}.")

if __name__ == "__main__":
    verify_groq_keys()
