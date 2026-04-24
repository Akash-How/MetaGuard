import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.services.mcp_agent import get_mcp_agent

async def test_slack_link():
    print("Initializing Agent...")
    agent = await get_mcp_agent()
    
    # Using a known channel ID from logs
    channel_id = "C0AEPMCU6UE" 
    query = f"Post a quick data health update to channel {channel_id}: 'System Check: All clear.' and make sure to give me the direct link."
    
    print(f"\nRunning Query: {query}...")
    response = await agent.run_loop(query)
    
    print(f"\nResponse:\n{response}")
    
    if "https://slack.com/archives/" in response:
        print("\nVerification SUCCESS: Permalink detected.")
    else:
        print("\nVerification FAILED: No permalink found in response.")

    await agent.close()

if __name__ == "__main__":
    asyncio.run(test_slack_link())
