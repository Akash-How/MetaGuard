import asyncio
import os
import json
from app.services.mcp_agent import McpAgent
from dotenv import load_dotenv

# Set working directory to backend
backend_root = r"c:\Users\amohanra\OneDrive - The Estée Lauder Companies Inc\Desktop\OpenMeta\backend"
os.chdir(backend_root)
load_dotenv(".env")

async def test_orchestrator():
    agent = McpAgent()
    print("Testing Orchestrator Multi-Turn capabilities...")
    
    # Test Case 1: Exact phrasing from user failure
    query = "Post a 'Data Health Check' summary to the project Slack channel"
    print(f"\nUser Query: {query}")
    
    try:
        response = await agent.run_loop(query, entity_id="warehouse.sales.raw.invoices_raw")
        print(f"\nAgent Response:\n{response}")
    except Exception as e:
        print(f"\nError during run_loop: {e}")
    
    # Test Case 2: Slack channel listing
    query2 = "What slack channels are available?"
    print(f"\nUser Query: {query2}")
    try:
        response2 = await agent.run_loop(query2, session_id="default")
        print(f"\nAgent Response:\n{response2}")
    except Exception as e:
        print(f"\nError during run_loop: {e}")

    await agent.close()

if __name__ == "__main__":
    asyncio.run(test_orchestrator())
