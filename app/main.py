# Last Update: 2026-09-07
"""FastAPI 진입점."""

from fastapi import FastAPI

from app.api import customers, recommend

app = FastAPI(title="Life-Embed-jh")
app.include_router(customers.router)
app.include_router(recommend.router)