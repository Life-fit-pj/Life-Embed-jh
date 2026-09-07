# Last Updated : 2026-09-07
"""고객 정보 API 응답 모양. customers 표 칸과 1:1 (app/tables/members.py:customer_one)."""

from datetime import date

from pydantic import BaseModel


class CustomerOut(BaseModel):
    customer_id: str
    name: str | None = None
    gender: str | None = None
    age: int | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    city_dong: str | None = None
    work_city: str | None = None
    work_dong: str | None = None
    joined_at: date | None = None