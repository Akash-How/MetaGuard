from fastapi import APIRouter

from app.schemas.modules import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter()
service = ChatService()


@router.post("/ask", response_model=ChatResponse)
async def ask_chat(payload: ChatRequest) -> ChatResponse:
    return await service.reply(payload)
