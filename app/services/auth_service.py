"""
Supabase Auth 로 인증된 사용자를 customer_id 에 연결한다.

토큰 검증(진짜 인증)은 app/ai/supabase_auth.py 가 한다 — 여기는 검증된 사용자를
user_login 표(app/tables/history.py)로 customer_id 와 잇는 "규칙"만 담당한다.
app/services/admin_service.py 가 이미 쓰는 것과 같은 구조.
"""

import random
import string

from app.services import admin_service

from app.repositories.history import create_login, get_login_row, login_customer_ids
from app.repositories.members import customer_ids


def _random_code(length, chars):
    return "".join(random.choice(chars) for _ in range(length))


def _login_id(supabase_user_id):
    """일반 아이디·backfill 로 발급된 아이디와 안 겹치게 접두어를 못박는다."""
    return f"supabase:{supabase_user_id}"


def login_with_supabase(supabase_user_id):
    """검증된 Supabase 사용자를 customer_id 에 연결한다. 가입한 적 없으면 None —
    예전처럼 처음 보는 사용자를 시드 회원에 즉석으로 붙이지 않는다. 그 자리는
    이제 signup() 이 진짜 회원가입으로 대신한다."""
    row = get_login_row(_login_id(supabase_user_id))
    return row["customer_id"] if row else None


def signed_up(supabase_user_id):
    """이 Supabase 사용자가 이미 가입돼 있는지. 회원가입 화면에서 로그인으로
    돌릴지 판단하는 데 쓴다."""
    return get_login_row(_login_id(supabase_user_id)) is not None


def signup(supabase_user_id, payload):
    """검증된 Supabase 사용자로 새 customer 를 만든다. 이미 가입돼 있으면 None(실패).

    payload(기본정보+희망조건+persona)로 customer 행 자체를 새로 만든다 —
    payload 모양은 app.services.admin_service.create_member() 와 같다. 비밀번호 칸은
    Supabase 가 이미 인증을 끝냈으므로 아무도 확인하지 않아 빈 값을 넣어 둔다.
    """
    login_id = _login_id(supabase_user_id)
    if get_login_row(login_id) is not None:
        return None
    member = admin_service.create_member(payload)
    customer_id = member["customer"]["customer_id"]
    create_login(customer_id, login_id, "")
    return customer_id


def backfill_logins():
    """user_login 이 없는 기존 customers 에게 임시 아이디/비번을 만들어 준다.

    로그인 시 즉석 발급(login)과 기존 시드 회원(C001~C099)이 같은 user_login
    표를 쓰므로, 이 표에 행이 없는 사람만 골라 채운다 — 이미 있는 사람은
    건너뛰어 두 번 실행해도 안전하다.
    """
    have = set(login_customer_ids())
    missing = [cid for cid in customer_ids() if cid not in have]

    issued = []
    for customer_id in missing:
        login_id = _random_code(6, string.ascii_lowercase + string.digits)
        password = _random_code(6, string.digits)
        create_login(customer_id, login_id, password)
        issued.append({"customer_id": customer_id, "login_id": login_id, "password": password})

    return issued
