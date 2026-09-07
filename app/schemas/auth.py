# Last Updated: 2026-09-08
"""인증 API 요청·응답 모양. app/features/auth.py 와 1:1."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    login_id: str
    password: str


class LoginOut(BaseModel):
    customer_id: str


class IdExistsOut(BaseModel):
    exists: bool


class SignupRequest(BaseModel):
    login_id: str
    password: str
    payload: dict   # customers 표 화이트리스트(app/features/admin.py CUSTOMER_FIELDS 등)


class SignupOut(BaseModel):
    customer_id: str
