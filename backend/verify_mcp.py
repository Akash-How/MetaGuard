import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.services.mcp_agent import get_mcp_agent

async def test_agent():
    print("Initializing Agent...")
    agent = await get_mcp_agent()
    
    print("\nListing Tools...")
    tools = await agent.get_all_tools()
    for t in tools:
        print(f"- {t['function']['name']}: {t['function']['description'][:50]}...")

    print("\nRunning Query: 'Find the data passport for warehouse.commerce.curated.fct_orders'...")
    response = await agent.run_loop("Find the data passport for warehouse.commerce.curated.fct_orders")
    print(f"\nResponse:\n{response}")

    print("\nRunning Query: 'Find tables that have failed DQ checks'...")
    response = await agent.run_loop("Find tables that have failed DQ checks")
    print(f"\nResponse:\n{response}")

    await agent.close()

if __name__ == "__main__":
    asyncio.run(test_agent())
