import asyncio
import os
import sys
import json

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.services.mcp_agent import get_mcp_agent

async def list_slack_tools():
    print("Initializing Agent...")
    agent = await get_mcp_agent()
    
    print("\nListing Slack Tools...")
    tools = await agent.get_all_tools()
    for t in tools:
        if "slack__" in t['function']['name']:
            print(f"- {t['function']['name']}")
            print(f"  Params: {json.dumps(t['function']['parameters'], indent=2)}")

    await agent.close()

if __name__ == "__main__":
    asyncio.run(list_slack_tools())
