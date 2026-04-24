import urllib.request
import json

data = json.dumps({"question": "Export all dead data assets to a Google Sheet", "session_id": "test1"}).encode('utf-8')

req = urllib.request.Request(
    'http://localhost:8000/api/chat/ask',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    with urllib.request.urlopen(req, timeout=60) as response:
        print("Success!")
        print(response.read().decode())
except Exception as e:
    print("Error:", str(e))
    if hasattr(e, 'read'):
        print(e.read().decode())
