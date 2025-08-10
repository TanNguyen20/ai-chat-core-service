from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from services.open_ai_service import OpenAIService
from utils.common import sse

router = APIRouter(prefix="/stream", tags=["stream"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}


@router.post("/ask-question", response_class=StreamingResponse)
async def ask_question_stream_response(request: Request):
    """
    Request JSON body: { "user_question": "..." }
    Response: text/event-stream with events: start, delta*, end, (error)
    """
    try:
        body = await request.json()
    except Exception:
        return StreamingResponse(
            iter([sse("error", {"message": "Invalid JSON body"}),
                  sse("end", {"finish_reason": "error"})]),
            media_type="text/event-stream",
            headers=_SSE_HEADERS,
        )

    user_question = (body.get("user_question") or "").strip()
    if not user_question:
        return StreamingResponse(
            iter([sse("error", {"message": "'user_question' is required"}),
                  sse("end", {"finish_reason": "error"})]),
            media_type="text/event-stream",
            headers=_SSE_HEADERS,
        )

    return StreamingResponse(
        OpenAIService.ask_question_stream_response(user_question),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
