from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import router as auth_router
from routers.comments import router as comments_router
from routers.invites import router as invites_router
from routers.tickets import router as tickets_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tickets_router)
app.include_router(comments_router)
app.include_router(invites_router)


@app.get("/health")
def health():
    return {"status": "ok"}