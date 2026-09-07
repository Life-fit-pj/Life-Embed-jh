# Last Update: 2026-09-07
"""FastAPI 진입점."""

from fastapi import FastAPI

from app.api import chat, customers, recommend, regions

app = FastAPI(title="Life-Embed-jh")
app.include_router(customers.router)
app.include_router(recommend.router)
app.include_router(regions.router)
app.include_router(chat.router)