# Last Updated: 2026-09-09
"""인증 API 요청·응답 모양. app/features/auth.py 와 1:1.

login_id·password 는 더 이상 안 받는다 — 인증은 Authorization 헤더의 Supabase
access token 으로 한다(app/api/auth.py 의 _supabase_id 참고).
"""

from pydantic import BaseModel


class LoginOut(BaseModel):
    customer_id: str


class SignedUpOut(BaseModel):
    signed_up: bool


class SignupRequest(BaseModel):
    payload: dict   # customers 표 화이트리스트(app/features/admin.py CUSTOMER_FIELDS 등)


class SignupOut(BaseModel):
    customer_id: str
