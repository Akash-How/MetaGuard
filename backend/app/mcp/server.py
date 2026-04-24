import asyncio
import sys
import logging
import os
from typing import Any
import httpx

from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configure logging to a file
logging.basicConfig(
    filename="mcp_server.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("metaguard_mcp")

from mcp.server.stdio import stdio_server
from mcp.server import Server, NotificationOptions
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

from app.services.passport import DataPassportService
from app.services.dead_data import DeadDataService
from app.services.blast_radius import BlastRadiusService
from app.services.storm_warning import get_storm_warning_service
from app.clients.openmetadata import get_openmetadata_client
from app.core.config import get_settings

settings = get_settings()

# Initialize services
passport_service = DataPassportService()
dead_data_service = DeadDataService()
blast_radius_service = BlastRadiusService()
storm_service = get_storm_warning_service()
om_client = get_openmetadata_client()

def _get_sheets_service():
    """Helper to authenticate with Google Sheets API."""
    creds_path = os.path.join(os.getcwd(), "google_credentials.json")
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Google credentials not found at {creds_path}")
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
    return build('sheets', 'v4', credentials=creds)

server = Server("metaguard")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_data_passport",
            description="Get a comprehensive business and technical summary for a data asset fqn.",
            inputSchema={
                "type": "object",
                "properties": {
                    "fqn": {"type": "string", "description": "The fully qualified name of the table or pipeline"}
                },
                "required": ["fqn"]
            }
        ),
        Tool(
            name="list_dead_data",
            description="Find unused or 'dead' data assets that are costing money and safe to delete.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_blast_radius",
            description="Analyze the downstream impact and risk of changes to a specific data asset.",
            inputSchema={
                "type": "object",
                "properties": {
                    "fqn": {"type": "string", "description": "The asset to analyze"}
                },
                "required": ["fqn"]
            }
        ),
        Tool(
            name="list_active_alerts",
            description="List recent data quality or freshness alerts (Storm Center).",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="search_entities",
            description="Search for OpenMetadata entities by keyword, domain, or data quality status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword (e.g. 'orders')"},
                    "tag": {"type": "string", "description": "Filter by tag (e.g. 'PII', 'gold')"},
                    "failed_dq": {
                        "type": "string", 
                        "description": "Filter for assets with failing quality checks. Provide as a string 'true' or 'false'."
                    }
                }
            }
        ),
        Tool(
            name="create_google_sheet",
            description="Create a new Google Sheet with specific data rows.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of the new spreadsheet (if creating new)"},
                    "spreadsheet_id": {
                        "type": "string", 
                        "description": "Optional: The ID of an existing sheet. Provide as a string. Omit this field if creating a new sheet."
                    },
                    "headers": {"type": "array", "items": {"type": "string"}, "description": "Column headers"},
                    "rows": {
                        "type": "array", 
                        "items": {"type": "array", "items": {"type": "string"}},
                        "description": "Data rows"
                    }
                },
                "required": ["title", "headers", "rows"]
            }
        ),
        Tool(
            name="post_to_slack_with_link",
            description="Post a message to Slack and return a direct permalink to the message.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string", "description": "The ID of the Slack channel (e.g. 'C012345')"},
                    "text": {"type": "string", "description": "The message text to post"}
                },
                "required": ["channel_id", "text"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    if not arguments:
        arguments = {}

    try:
        if name == "get_data_passport":
            fqn = arguments.get("fqn")
            passport = passport_service.get_passport(fqn)
            metadata_str = str(passport.metadata)[:2000] # Ensure we include ownership, tags, columns
            return [TextContent(type="text", text=f"Passport for {fqn}:\n\nSummary: {passport.summary}\nTrust Score: {passport.trust_score.total}\nImpact: {passport.impact_score}/10\nDetailed Data: {metadata_str}")]

        elif name == "list_dead_data":
            scan = dead_data_service.scan()
            summary = "\n".join([f"- {a.fqn} ({a.category}): ${a.monthly_cost_estimate}/mo" for a in scan.assets[:10]])
            return [TextContent(type="text", text=f"Top Dead Data Assets:\n{summary}")]

        elif name == "get_blast_radius":
            fqn = arguments.get("fqn")
            report = blast_radius_service.get_table_report(fqn)
            nodes_str = ", ".join([f"{n.fqn} ({n.impact_type})" for n in report.nodes])
            return [TextContent(type="text", text=f"Blast Radius for {fqn}:\nRisk Score: {report.overall_risk_score}\nImpacted Assets: {report.total_impacted_assets}\nDownstream Feeders: {nodes_str}")]

        elif name == "list_active_alerts":
            feed = storm_service.list_alerts()
            summary = "\n".join([f"- [{a.severity}] {a.summary} ({a.fqn})" for a in feed.alerts[:5]])
            return [TextContent(type="text", text=f"Storm Center Alerts:\n{summary}")]

        elif name == "search_entities":
            query = arguments.get("query", "").lower()
            tag = arguments.get("tag", "").lower()
            
            # Robust boolean casting for AI string inputs
            failed_dq = arguments.get("failed_dq", False)
            if isinstance(failed_dq, str):
                failed_dq = failed_dq.lower() in ("true", "yes", "1")
            
            tables = om_client.list_all_tables()
            results = []
            for t in tables:
                if query and query not in t["fqn"].lower() and query not in t.get("description", "").lower():
                    continue
                if tag and tag not in [tg.lower() for tg in t.get("tags", [])]:
                    continue
                if failed_dq:
                    quality = om_client.get_quality(t["fqn"])
                    if quality.get("pass_rate", 1.0) >= 1.0:
                        continue
                results.append(t["fqn"])
            
            return [TextContent(type="text", text="Search Results:\n" + "\n".join(results[:15]))]

        elif name == "create_google_sheet":
            title = arguments.get("title", "MetaGuard Export")
            spreadsheet_id = arguments.get("spreadsheet_id")
            
            # Robust normalization for AI 'hallucinated' empty lists/arrays
            if isinstance(spreadsheet_id, list) or (isinstance(spreadsheet_id, str) and not spreadsheet_id.strip()):
                spreadsheet_id = settings.default_spreadsheet_id
            elif not spreadsheet_id:
                spreadsheet_id = settings.default_spreadsheet_id
                
            headers = arguments.get("headers", [])
            rows = arguments.get("rows", [])
            
            # Use retries for corporate network stability
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    logger.info(f"Attempting Google Sheet export (Attempt {attempt+1}/{max_retries})...")
                    service = _get_sheets_service()
                    
                    if not spreadsheet_id:
                        # Create if no ID
                        spreadsheet = {'properties': {'title': title}}
                        spreadsheet = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
                        spreadsheet_id = spreadsheet.get('spreadsheetId')
                        msg_prefix = f"Success! Created new Spreadsheet: '{title}'."
                    else:
                        msg_prefix = f"Success! Exported to existing Sheet."
                    
                    # Clear the sheet first so old data doesn't persist
                    if spreadsheet_id == settings.default_spreadsheet_id:
                        service.spreadsheets().values().clear(
                            spreadsheetId=spreadsheet_id,
                            range="A:Z"
                        ).execute()

                    # Update data
                    values = [headers] + rows
                    body = {'values': values}
                    service.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id, 
                        range="A1",
                        valueInputOption="RAW", 
                        body=body
                    ).execute()
                    
                    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
                    return [TextContent(type="text", text=f"{msg_prefix}\n\n[📊 View your Google Sheet]({sheet_url})")]
                
                except Exception as e:
                    logger.warning(f"Google Sheet attempt {attempt+1} failed: {str(e)}")
                    if attempt == max_retries - 1:
                        raise e
                    await asyncio.sleep(1) # Wait before retry

        elif name == "post_to_slack_with_link":
            channel_id = arguments.get("channel_id")
            text = arguments.get("text")
            token = settings.slack_bot_token

            if not token:
                return [TextContent(type="text", text="Error: SLACK_BOT_TOKEN not configured in backend.")]

            async with httpx.AsyncClient() as client:
                # 1. Post the message
                post_resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"channel": channel_id, "text": text}
                )
                post_data = post_resp.json()
                
                if not post_data.get("ok"):
                    return [TextContent(type="text", text=f"Slack Post Error: {post_data.get('error')}")]

                msg_ts = post_data.get("ts")

                # 2. Get the permalink
                link_resp = await client.get(
                    "https://slack.com/api/chat.getPermalink",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"channel": channel_id, "message_ts": msg_ts}
                )
                link_data = link_resp.json()
                permalink = link_data.get("permalink", "Link generation failed.")

                return [TextContent(type="text", text=f"SUCCESS: Message posted to {channel_id}.\n[🔗 View on Slack]({permalink})")]

        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]

async def main():
    logger.info("Starting MetaGuard MCP Server...")
    try:
        async with stdio_server() as (read_stream, write_stream):
            init_options = server.create_initialization_options(
                notification_options=NotificationOptions(resources_changed=True, prompts_changed=True, tools_changed=True)
            )
            logger.info("Running server with stdio...")
            await server.run(
                read_stream,
                write_stream,
                init_options
            )
    except Exception as e:
        logger.exception("Server crashed with error")

if __name__ == "__main__":
    asyncio.run(main())
