import asyncio
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.services.dead_data import DeadDataService
from app.mcp.server import _get_sheets_service
from app.core.config import get_settings

async def sync_dead_data_to_premade_sheet():
    settings = get_settings()
    spreadsheet_id = settings.default_spreadsheet_id
    
    print("Initializing Dead Data Scan...")
    service = DeadDataService()
    
    try:
        # 1. Run the scan
        scan_results = service.scan()
        print(f"Success: Scan complete. Found {scan_results.total_candidates} candidates.")
        
        # 2. Prepare headers and rows
        headers = [
            "FQN", 
            "Type", 
            "Category", 
            "Owner", 
            "Monthly Waste ($)", 
            "Confidence", 
            "Impact Score", 
            "Safe to Delete?"
        ]
        
        rows = []
        for asset in scan_results.assets:
            rows.append([
                asset.fqn,
                asset.asset_type,
                asset.category,
                asset.owner or "N/A",
                str(asset.monthly_cost_estimate or 0.0),
                asset.confidence,
                str(asset.impact_score),
                "YES" if asset.safe_to_delete else "NO (Review Required)"
            ])
            
        print(f"Prepared {len(rows)} rows for export.")
        
        # 3. Push to Google Sheets
        service_sheets = _get_sheets_service()
        
        # Clear existing data first
        print(f"Clearing existing data in sheet {spreadsheet_id}...")
        service_sheets.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range="A:Z"
        ).execute()
        
        # Update with new data
        values = [headers] + rows
        body = {'values': values}
        
        print(f"Exporting results to sheet...")
        service_sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, 
            range="A1",
            valueInputOption="RAW", 
            body=body
        ).execute()
        
        sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
        print(f"\nSUCCESS! MetaGuard Dead Data has been synced.")
        print(f"URL: {sheet_url}")
        
    except Exception as e:
        print(f"Error during sync: {str(e)}")

if __name__ == "__main__":
    asyncio.run(sync_dead_data_to_premade_sheet())
