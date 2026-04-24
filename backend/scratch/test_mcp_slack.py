import asyncio
import os
import json
from app.services.mcp_agent import McpAgent
from dotenv import load_dotenv

# Set working directory to backend
backend_root = r"c:\Users\amohanra\OneDrive - The Estée Lauder Companies Inc\Desktop\OpenMeta\backend"
os.chdir(backend_root)
load_dotenv(".env")

async def test_tools():
    agent = McpAgent()
    print("Connecting to servers...")
    await agent.connect_servers()
    print(f"Connected to sessions: {list(agent.sessions.keys())}")
    
    tools = await agent.get_all_tools()
    for tool in tools:
        name = tool["function"]["name"]
        if name in ["slack__slack_post_message", "slack__slack_list_channels", "slack__slack_get_channel_history"]:
            print(f"\nSlack Tool Schema: {name}")
            print(json.dumps(tool["function"]["parameters"], indent=2))
            
    await agent.close()

if __name__ == "__main__":
    asyncio.run(test_tools())
