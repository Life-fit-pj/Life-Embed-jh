# Last Updated: 2026-09-08
"""인증 라우트."""

from fastapi import APIRouter, HTTPException

from app.features.auth import id_exists, login, signup
from app.schemas.auth import IdExistsOut, LoginOut, LoginRequest, SignupOut, SignupRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def post_login(body: LoginRequest):
    """아이디+비번으로 로그인. 처음 보는 아이디면 그 자리에서 발급도 겸한다."""
    customer_id = login(body.login_id, body.password)
    if customer_id is None:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 맞지 않다")
    return {"customer_id": customer_id}

@router.get("/id-exists/{login_id}", response_model=IdExistsOut)
def get_id_exists(login_id: str):
    """아이디 중복확인. 회원가입 화면의 '중복확인' 버튼이 부른다."""
    return {"exists": id_exists(login_id)}

@router.post("/signup", response_model=SignupOut)
def post_signup(body: SignupRequest):
    """아이디+비밀번호+회원정보로 새 계정을 만든다. 이미 있는 아이디면 409."""
    customer_id = signup(body.login_id, body.password, body.payload)
    if customer_id is None:
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디다")
    return {"customer_id": customer_id}
