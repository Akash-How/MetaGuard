import asyncio
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.services.chat import ChatService
from app.schemas.modules import ChatRequest

async def test_memory():
    print("Testing MetaGuard Conversational Memory...")
    service = ChatService()
    session_id = "test-session-123"

    # Turn 1: Tell the bot something
    print("\nTurn 1: Setting context...")
    req1 = ChatRequest(question="My favorite data table is 'warehouse.raw.users'. Remember that.", session_id=session_id)
    resp1 = await service.reply(req1)
    print(f"Assistant: {resp1.answer}")

    # Turn 2: Ask the bot to recall
    print("\nTurn 2: Recalling context...")
    req2 = ChatRequest(question="What is my favorite data table?", session_id=session_id)
    resp2 = await service.reply(req2)
    print(f"Assistant: {resp2.answer}")

    if "users" in resp2.answer.lower():
        print("\nSUCCESS: Memory verified!")
    else:
        print("\nFAILURE: Memory not working.")

if __name__ == "__main__":
    asyncio.run(test_memory())
