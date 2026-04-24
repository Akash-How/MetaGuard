import sys
sys.path.insert(0, "C:/Users/amohanra/OneDrive - The Estée Lauder Companies Inc/Desktop/OpenMeta/backend")
from app.services.dead_data import DeadDataService

try:
    print("Testing DeadDataService scan()...")
    service = DeadDataService()
    results = service.scan()
    print("Monthly Waste:", results.get('summary', {}).get('monthly_waste_estimate'))
    print("Zombie Pipelines:", results.get('summary', {}).get('zombie_pipelines_count'))
    for item in results.get('assets', []):
        print(item['fqn'], "Cost:", item['monthly_cost_estimate'])
except Exception as e:
    print("Error:", str(e))
