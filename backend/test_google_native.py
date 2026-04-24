import asyncio
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.mcp.server import _get_sheets_service

def test_google_sheet_direct():
    print("Testing Google Sheets Native Integration (Direct Call)...")
    try:
        creds_path = os.path.join(os.getcwd(), "google_credentials.json")
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
        service = build('sheets', 'v4', credentials=creds)
        print("Successfully authenticated with Google.")
        
        title = "MetaGuard Native Test Export"
        spreadsheet_id = "1a-RPfc16qIuwwKTMqoSvOi4nCr6pntgcs3OkVvj2W6Q"
        
        headers = ["Table Name", "Trust Score", "Status"]
        rows = [
            ["warehouse.sales.raw.invoices_raw", "53", "Healthy"],
            ["warehouse.commerce.curated.fct_orders", "94", "Healthy"]
        ]
        values = [headers] + rows
        body = {'values': values}
        
        print(f"Updating data in existing sheet {spreadsheet_id}...")
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, 
            range="A1",
            valueInputOption="RAW", 
            body=body
        ).execute()
        
        sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
        print(f"\nSUCCESS! Created Google Sheet: {sheet_url}")
        
    except Exception as e:
        print(f"\nFAILED: {str(e)}")

if __name__ == "__main__":
    test_google_sheet_direct()
