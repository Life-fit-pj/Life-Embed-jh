# Last Update: 2026-09-07
"""FastAPI 진입점."""

from fastapi import FastAPI

from app.api import auth, chat, customers, history, recommend, regions, survey

app = FastAPI(title="Life-Embed-jh")
app.include_router(customers.router)
app.include_router(recommend.router)
app.include_router(regions.router)
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(survey.router)
app.include_router(history.router)