# Last Updated: 2026-09-09
"""인증 API 요청·응답 모양. app/services/auth_service.py 와 1:1.

login_id·password 는 더 이상 안 받는다 — 인증은 Authorization 헤더의 Supabase
access token 으로 한다(app/api/auth.py 의 _supabase_id 참고).
"""

from pydantic import BaseModel

from app.schemas.customers import CustomerOut


class LoginOut(BaseModel):
    customer_id: str


class SignedUpOut(BaseModel):
    signed_up: bool


class SignupRequest(BaseModel):
    payload: dict   # customers 표 화이트리스트(app/services/admin_service.py CUSTOMER_FIELDS 등)


class SignupOut(BaseModel):
    customer_id: str


class MeOut(BaseModel):
    """회원 본인 조회. persona 는 가입 설문 아홉 칸 중 글이 있는 것만 — activity_persona 는 관리자 전용이라 안 준다"""
    customer_id: str
    customer: CustomerOut
    persona: dict[str, str]
