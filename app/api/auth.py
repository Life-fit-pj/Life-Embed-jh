# Last Updated: 2026-09-09
"""인증 라우트. Supabase 가 발급한 access token 을 Authorization 헤더로 받아 검증한다."""

from fastapi import APIRouter, Depends, Header, HTTPException

from app.ai.supabase_auth import verify_token
from app.schemas.auth import LoginOut, SignedUpOut, SignupOut, SignupRequest
from app.services.auth_service import login_with_supabase, signed_up, signup

router = APIRouter(prefix="/auth", tags=["auth"])


def _supabase_id(authorization: str = Header(...)) -> str:
    """Authorization: Bearer <supabase access token> 에서 검증된 사용자 id 를 뽑는다."""
    token = authorization.removeprefix("Bearer ").strip()
    user = verify_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="로그인 토큰이 유효하지 않다")
    return user["id"]


@router.post("/login", response_model=LoginOut)
def post_login(supabase_id: str = Depends(_supabase_id)):
    """이미 가입된 Supabase 사용자를 customer_id 에 연결한다."""
    customer_id = login_with_supabase(supabase_id)
    if customer_id is None:
        raise HTTPException(status_code=404, detail="가입된 계정이 아니다")
    return {"customer_id": customer_id}


@router.get("/signed-up", response_model=SignedUpOut)
def get_signed_up(supabase_id: str = Depends(_supabase_id)):
    """회원가입 화면에서, 이미 가입된 사용자면 로그인으로 돌리는 데 쓴다."""
    return {"signed_up": signed_up(supabase_id)}


@router.post("/signup", response_model=SignupOut)
def post_signup(body: SignupRequest, supabase_id: str = Depends(_supabase_id)):
    """Supabase 인증 + 회원정보로 새 계정을 만든다. 이미 가입돼 있으면 409."""
    customer_id = signup(supabase_id, body.payload)
    if customer_id is None:
        raise HTTPException(status_code=409, detail="이미 가입된 계정이다")
    return {"customer_id": customer_id}
