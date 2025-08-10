from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware

from services.mcp_use import stream_superset_dashboards
from services.open_ai_service import OpenAIService
from utils.common import sse

app = FastAPI()

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # set False if you won't use cookies/auth
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "X-Api-Key",
        "Authorization",
        "Accept",
    ],
    expose_headers=[  # optional: expose any custom response headers
        "Content-Type",
        "Cache-Control",
        "Connection",
    ],
)


@app.get("/", response_class=StreamingResponse)
async def root():
    return StreamingResponse(
        stream_superset_dashboards(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/stream/ask-question", response_class=StreamingResponse)
async def ask_question_stream_response(request: Request):
    """
    Request JSON body: { "user_question": "..." }
    Response: text/event-stream with events: start, delta*, end, (error)
    """
    try:
        body = await request.json()
    except Exception:
        return StreamingResponse(
            iter([sse("error", {"message": "Invalid JSON body"}), sse("end", {"finish_reason": "error"})]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    user_question = (body.get("user_question") or "").strip()
    if not user_question:
        return StreamingResponse(
            iter([sse("error", {"message": "'user_question' is required"}), sse("end", {"finish_reason": "error"})]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    return StreamingResponse(
        OpenAIService.ask_question_stream_response(user_question),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
