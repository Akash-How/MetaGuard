import urllib.request
import json

try:
    req = urllib.request.Request('http://localhost:8000/api/dead-data/scan')
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode())
        print("Monthly Waste:", data.get("summary", {}).get("monthly_waste_estimate"))
        print("Zombie Pipelines:", data.get("summary", {}).get("zombie_pipelines_count"))
except Exception as e:
    print("Error:", str(e))
