"""
임시 로그인 발급/검증.

이 파일은 "규칙"만 담당한다 — SQL은 app/repositories/ 에 있다.
app/features/admin.py 가 이미 쓰는 것과 같은 구조.
"""

import random
import string

from app.features import admin

from app.repositories.history import pick_customer_for_login, create_login, get_login_row, login_customer_ids
from app.repositories.members import customer_ids


def _random_code(length, chars):
    return "".join(random.choice(chars) for _ in range(length))


def login(login_id, password):
    """아이디+비번으로 로그인한다. 성공하면 customer_id, 실패하면 None.

    처음 보는 아이디면 그 자리에서 기존 회원(이름·나이·페르소나가 이미 있는
    시드 데이터)에게 이 아이디/비번을 붙여 바로 로그인시킨다 — 로그인이 없는
    회원이 남아 있으면 그 사람에게, 다 배정됐으면 로그인이 가장 적게 붙은
    회원을 다시 쓴다. 빈 계정은 절대 새로 만들지 않는다(마이페이지는 그
    회원의 기존 정보를 그대로 보여줄 뿐이라 정보가 있는 회원이어야 의미가
    있다). 이미 있는 아이디면 비번이 맞는지만 본다. 별도 "계정 발급" 단계
    없이 로그인 폼 하나로 발급+로그인을 겸하는 게 지금 요구사항이다 —
    실 회원가입이 붙으면 이 즉석 발급 분기는 걷어내면 된다.
    """
    row = get_login_row(login_id)
    if row is None:
        customer_id = pick_customer_for_login()
        create_login(customer_id, login_id, password)
        return customer_id

    return row["customer_id"] if row["password"] == password else None


def id_exists(login_id):
    """이 아이디가 이미 쓰이고 있는지. 회원가입 화면의 '중복확인' 버튼이 부른다."""
    return get_login_row(login_id) is not None


def signup(login_id, password, payload):
    """새 아이디로 명시적으로 가입한다. 이미 있는 아이디면 None(실패).

    이전에는 login() 처럼 이미 있는 시드 회원(C001~)에게 로그인만 붙이는
    즉석 발급이었다. 이제는 payload(기본정보+희망조건+persona)로 customer 행
    자체를 새로 만든다 — payload 모양은 app.features.admin.create_member() 와 같다.
    """
    if get_login_row(login_id) is not None:
        return None
    member = admin.create_member(payload)
    customer_id = member["customer"]["customer_id"]
    create_login(customer_id, login_id, password)
    return customer_id


def google_login(email):
    """구글 계정(이메일)으로 로그인한다. 처음이면 그 자리에서 계정을 배정하고,
    다음부터는 같은 이메일이 항상 같은 계정으로 돌아온다.

    아이디/비번 로그인과 같은 user_login 표를 쓰되, login_id 를 "google:이메일"
    형태로 못박아 일반 아이디와 겹치지 않게 한다. 비밀번호 칸은 이 경로로는 아무도
    확인하지 않으므로(구글 토큰 검증이 곧 인증이다) 아무도 못 맞힐 무작위 값을 넣어 둔다.
    """
    login_id = f"google:{email}"
    row = get_login_row(login_id)
    if row is not None:
        return row["customer_id"]

    customer_id = pick_customer_for_login()
    create_login(customer_id, login_id, _random_code(24, string.ascii_letters + string.digits))
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
