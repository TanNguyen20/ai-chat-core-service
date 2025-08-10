from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from controllers.root_controller import router as root_router
from controllers.question_controller import router as question_router

app = FastAPI()

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5500",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Api-Key", "Authorization", "Accept"],
    expose_headers=["Content-Type", "Cache-Control", "Connection"],
)

# mount controllers
app.include_router(root_router)
app.include_router(question_router)
