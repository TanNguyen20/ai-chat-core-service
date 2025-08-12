from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from services.mcp_use import stream_mcp

router = APIRouter(tags=["root"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}


@router.get("/", response_class=StreamingResponse)
async def root():
    return StreamingResponse(
        stream_mcp(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
