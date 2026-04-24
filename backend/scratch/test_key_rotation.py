import sys
import os
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.config import Settings
from app.clients.llm import LLMClient

def test_key_parsing():
    print("--- Testing Key Parsing ---")
    settings = Settings(
        google_api_key="key1, key2,  key3",
        groq_api_key="groq1,groq2"
    )
    print(f"Google Keys: {settings.google_api_key_list}")
    print(f"Groq Keys: {settings.groq_api_key_list}")
    
    assert settings.google_api_key_list == ["key1", "key2", "key3"]
    assert settings.groq_api_key_list == ["groq1", "groq2"]
    print("SUCCESS: Parsing works correctly.\n")

def test_rotation_logic():
    print("--- Testing Rotation Logic ---")
    
    # Mock settings with multiple keys
    mock_settings = MagicMock()
    mock_settings.google_api_key_list = ["bad_key", "good_key"]
    mock_settings.groq_api_key_list = []
    
    with patch('app.clients.llm.get_settings', return_value=mock_settings):
        client = LLMClient()
        
        # Mock httpx response to fail on first key (429) then succeed on second
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 429
        
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Success Response"}]}}]
        }
        
        # Side effect: 1st call fails, 2nd succeeds
        client.client.post = MagicMock(side_effect=[mock_response_fail, mock_response_ok])
        
        result = client._generate_gemini("sys", "user", "model", 100)
        
        print(f"Result: {result}")
        print(f"Post call count: {client.client.post.call_count}")
        print(f"Current Key Index after rotation: {client._current_google_idx}")
        
        assert result == "Success Response"
        assert client.client.post.call_count == 2
        assert client._current_google_idx == 1
        print("SUCCESS: Rotation and retry successful.\n")

if __name__ == "__main__":
    try:
        test_key_parsing()
        test_rotation_logic()
    except Exception as e:
        print(f"FAILURE: {e}")
        import traceback
        traceback.print_exc()
